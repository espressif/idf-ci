# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import glob
import json
import logging
import os
import re
import subprocess
import tempfile
import time
import typing as t
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import esp_bool_parser
import minio
import requests
import urllib3
from gitlab import Gitlab
from minio import Minio

from .._compat import UNDEF, is_undefined
from .._vendor import translate
from ..envs import GitlabEnvVars
from ..settings import get_ci_settings
from ..utils import get_current_branch

logger = logging.getLogger(__name__)


def execute_concurrent_tasks(
    tasks: t.List[t.Callable[..., t.Any]],
    max_workers: t.Optional[int] = None,
    task_name: str = 'executing task',
) -> t.List[t.Any]:
    """Execute tasks concurrently using ThreadPoolExecutor.

    :param tasks: List of callable tasks to execute
    :param max_workers: Maximum number of worker threads
    :param task_name: Error message prefix for logging

    :returns: List of successful task results; order is not guaranteed
    """
    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]

        for future in as_completed(futures):
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f'Error while {task_name}: {e}')
                errors.append(e)

    if errors:
        _nl = '\n'  # compatible with Python < 3.12
        raise ArtifactError(f'Got {len(errors)} errors while {task_name}:\n{_nl.join([f"- {e}" for e in errors])}')

    return results


@dataclass
class ArtifactParams:
    """Common parameters for artifacts operations.

    The commit SHA can be determined in the following order of precedence:

    1. Explicitly provided commit_sha parameter
    2. PIPELINE_COMMIT_SHA environment variable
    3. Latest commit from branch (where branch is determined by branch parameter or
       current git branch)
    """

    commit_sha: t.Optional[str] = None
    branch: t.Optional[str] = None
    folder: t.Optional[str] = None

    def __post_init__(self):
        if self.folder is None:
            self.folder = os.getcwd()
        self.from_path = Path(self.folder)

        # Get commit SHA with the following precedence:
        # 1. CLI provided commit_sha
        if self.commit_sha:
            return

        # 2. Environment variable PIPELINE_COMMIT_SHA
        if os.getenv('PIPELINE_COMMIT_SHA'):
            self.commit_sha = os.environ['PIPELINE_COMMIT_SHA']
            return

        # 3. Latest commit from branch
        try:
            if self.branch is None:
                self.branch = get_current_branch()
            result = subprocess.run(
                ['git', 'rev-parse', self.branch],
                check=True,
                capture_output=True,
                encoding='utf-8',
            )
            self.commit_sha = result.stdout.strip()
        except Exception:
            raise ValueError(
                'Failed to get commit SHA from git command. '
                'Must set commit_sha or branch parameter, or set PIPELINE_COMMIT_SHA env var'
            )


class ArtifactError(RuntimeError):
    """Base exception for artifact-related errors."""


class S3Error(ArtifactError):
    """Exception raised for S3-related errors."""


class PresignedUrlError(ArtifactError):
    """Exception raised for presigned URL-related errors."""


class ArtifactManager:
    def __init__(self):
        self.envs = GitlabEnvVars()
        self.settings = get_ci_settings()

        self._s3_client: t.Optional[Minio] = UNDEF  # type: ignore
        self._s3_public_client: t.Optional[Minio] = UNDEF  # type: ignore

    @property
    @lru_cache()
    def gl(self):
        return Gitlab(
            self.envs.GITLAB_HTTPS_SERVER,
            private_token=self.envs.GITLAB_ACCESS_TOKEN,
        )

    @property
    @lru_cache()
    def project(self):
        project = self.gl.projects.get(self.settings.gitlab.project)
        if not project:
            raise ValueError(f'Project {self.settings.gitlab.project} not found')
        return project

    @property
    def s3_client(self) -> t.Optional[minio.Minio]:
        if is_undefined(self._s3_client):
            self._s3_client = self._create_s3_client()
        return self._s3_client

    @property
    def s3_public_client(self) -> t.Optional[minio.Minio]:
        if is_undefined(self._s3_public_client):
            self._s3_public_client = self._create_s3_client(public=True)
        return self._s3_public_client

    def _create_s3_client(self, *, public=False) -> t.Optional[minio.Minio]:
        if not self.envs.IDF_S3_SERVER:
            logger.info('S3 credentials not available. Skipping S3 features...')
            return None

        if not public:
            if not all(
                [
                    self.envs.IDF_S3_ACCESS_KEY,
                    self.envs.IDF_S3_SECRET_KEY,
                ]
            ):
                logger.info('S3 credentials not available. Skipping S3 features...')
                return None

        if self.envs.IDF_S3_SERVER.startswith('https://'):
            host = self.envs.IDF_S3_SERVER.replace('https://', '')
            secure = True
        elif self.envs.IDF_S3_SERVER.startswith('http://'):
            host = self.envs.IDF_S3_SERVER.replace('http://', '')
            secure = False
        else:
            raise ValueError('Please provide a http or https server URL for S3')

        logger.debug('S3 Host: %s', host)
        return minio.Minio(
            host,
            access_key=self.envs.IDF_S3_ACCESS_KEY if not public else '',
            secret_key=self.envs.IDF_S3_SECRET_KEY if not public else '',
            secure=secure,
            http_client=urllib3.PoolManager(
                num_pools=10,
                maxsize=10,
                timeout=urllib3.Timeout(
                    total=self.envs.IDF_S3_TIMEOUT_TOTAL,
                ),
                retries=urllib3.Retry(
                    total=5,
                    backoff_factor=1,
                    status_forcelist=(408, 429, 500, 502, 503, 504),
                ),
            ),
        )

    def _get_patterns_for_type(self, artifact_type: str) -> t.List[str]:
        config = self.settings.gitlab.artifacts.s3.configs[artifact_type]

        if not config.base_dir_pattern:
            return config.patterns

        return [os.path.join(config.base_dir_pattern, pattern) for pattern in config.patterns]

    def _get_artifact_types(self, artifact_type: t.Optional[str]) -> t.List[str]:
        if artifact_type and artifact_type not in self.settings.gitlab.artifacts.s3.configs:
            raise ValueError(
                f'Invalid artifact type: {artifact_type}. '
                f'Available types: {list(self.settings.gitlab.artifacts.s3.configs.keys())}'
            )

        available_types = []
        for art_type, config in self.settings.gitlab.artifacts.s3.configs.items():
            # Check if_clause condition
            if config.if_clause:
                try:
                    stmt = esp_bool_parser.parse_bool_expr(config.if_clause)
                    res = stmt.get_value('', '')
                except Exception as e:
                    logger.debug(
                        f'Skipping {art_type} artifacts due to error '
                        f'while evaluating if_clause: {config.if_clause}: {e}'
                    )
                else:
                    if res:
                        available_types.append(art_type)
                    else:
                        logger.debug(f'Skipping {art_type} artifacts due to if_clause: {config.if_clause}')
            else:
                available_types.append(art_type)

        if artifact_type:
            if artifact_type in available_types:
                return [artifact_type]
            else:
                return []

        return available_types

    def _get_s3_path(self, prefix: str, from_path: Path) -> str:
        if from_path.is_absolute():
            # Resolve IDF_PATH to absolute path to ensure relative_to() works correctly
            idf_path = Path(self.envs.IDF_PATH).resolve() if self.envs.IDF_PATH else Path.cwd()
            rel_path = str(from_path.relative_to(idf_path))
        else:
            rel_path = str(from_path)

        return f'{prefix}{rel_path}' if rel_path != '.' else prefix

    def _download_files_from_s3(
        self,
        *,
        prefix: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        config = self.settings.gitlab.artifacts.s3.configs[artifact_type]
        s3_client = self._validate_s3_client(artifact_type)

        def _download_task(_obj_name: str, _output_path: Path) -> None:
            logger.debug(f'Downloading {_obj_name} to {_output_path}')
            _output_path.parent.mkdir(parents=True, exist_ok=True)
            s3_client.fget_object(config.bucket, _obj_name, str(_output_path))

        tasks = []
        patterns_regexes = [
            re.compile(translate(pattern, recursive=True, include_hidden=True))
            for pattern in self._get_patterns_for_type(artifact_type)
        ]
        for obj in s3_client.list_objects(config.bucket, prefix=self._get_s3_path(prefix, from_path), recursive=True):
            output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
            if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                continue
            tasks.append(
                lambda _obj_name=obj.object_name, _output_path=output_path: _download_task(_obj_name, _output_path)
            )

        execute_concurrent_tasks(tasks, task_name='downloading object')
        return len(tasks)

    def _extract_zip_file(self, zip_path: Path) -> None:
        logger.debug(f'Extracting {zip_path}')
        try:
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(zip_path.parent)
        except zipfile.BadZipFile as e:
            logger.error(f'Failed to extract {zip_path}: {e}')
            raise
        finally:
            zip_path.unlink()
            logger.debug(f'Removed zip file {zip_path}')

    def _download_zip_from_s3(
        self,
        *,
        prefix: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        """Download and extract zip files from S3."""
        config = self.settings.gitlab.artifacts.s3.configs[artifact_type]
        s3_client = self._validate_s3_client(artifact_type)

        def _download_and_extract(obj_name: str, zip_path: Path) -> None:
            logger.debug(f'Downloading {obj_name} to {zip_path}')
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            s3_client.fget_object(config.bucket, obj_name, str(zip_path))
            self._extract_zip_file(zip_path)

        # Find matching zip files
        tasks = []
        # Look for zip files matching artifact types (e.g., flash.zip, debug.zip)
        # Since we're listing recursively, just check if filename matches {art_type}.zip
        for obj in s3_client.list_objects(config.bucket, prefix=self._get_s3_path(prefix, from_path), recursive=True):
            output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
            if output_path.name == f'{artifact_type}.zip':
                tasks.append(lambda o=obj.object_name, op=output_path: _download_and_extract(o, op))

        execute_concurrent_tasks(tasks, task_name='downloading and extracting zip')
        return len(tasks)

    def _validate_s3_client(self, artifact_type: str) -> minio.Minio:
        config = self.settings.gitlab.artifacts.s3.configs[artifact_type]
        if config.is_public:
            if not self.s3_public_client:
                raise S3Error('S3 public client is not configured properly')
            return self.s3_public_client
        else:
            if not self.s3_client:
                raise S3Error('S3 client is not configured properly')
            return self.s3_client

    def _upload_files_to_s3(
        self,
        *,
        prefix: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        config = self.settings.gitlab.artifacts.s3.configs[artifact_type]
        s3_client = self._validate_s3_client(artifact_type)

        def _upload_task(_filepath: Path, _s3_path: str) -> None:
            logger.debug(f'Uploading {_filepath} to {_s3_path}')
            s3_client.fput_object(config.bucket, _s3_path, str(_filepath))

        tasks = []
        for pattern in config.patterns:
            if config.base_dir_pattern:
                pattern = os.path.join(config.base_dir_pattern, pattern)

            abs_pattern = os.path.join(str(from_path), pattern)
            for file_str in glob.glob(abs_pattern, recursive=True):
                filepath = Path(file_str)
                if not filepath.is_file():
                    continue

                s3_path = self._get_s3_path(prefix, filepath)
                tasks.append(lambda _filepath=filepath, _s3_path=s3_path: _upload_task(_filepath, _s3_path))

        execute_concurrent_tasks(tasks, task_name='uploading file')
        return len(tasks)

    def _upload_zip_to_s3(
        self,
        *,
        prefix: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        """Upload artifacts as zip files to S3.

        This method:

        1. Finds directories matching ``base_dir_pattern`` (only folders).
        2. For each directory, finds files matching ``patterns`` (relative to that
           directory).
        3. Creates a zip file named ``<artifact_type>.zip`` in that directory.
        4. Uploads the zip file to S3.

        :param prefix: S3 prefix path
        :param from_path: Base path to search from
        :param artifact_type: Type of artifact (used as zip filename)

        :returns: Number of zip files uploaded
        """
        config = self.settings.gitlab.artifacts.s3.configs[artifact_type]
        s3_client = self._validate_s3_client(artifact_type)

        def _upload_zip_task(_zip_path: Path, _s3_path: str) -> None:
            logger.debug(f'Uploading zip {_zip_path} to {_s3_path}')
            s3_client.fput_object(config.bucket, _s3_path, str(_zip_path))

        tasks = []
        # Find all directories matching base_dir_pattern
        # The pattern should match directories only (e.g., '**/build*/')
        if not config.base_dir_pattern:
            matching_dirs = [from_path.resolve()]
        else:
            abs_pattern = os.path.realpath(str(Path(from_path) / config.base_dir_pattern))
            # Remove trailing slash if present for glob matching
            # Pattern like '**/build*/' should match directories starting with 'build'
            pattern_for_glob = abs_pattern.rstrip('/')

            # Use glob to find all matches, then filter for directories only
            matching_dirs = [
                Path(match).resolve() for match in glob.glob(pattern_for_glob, recursive=True) if Path(match).is_dir()
            ]

        logger.debug(f'Found {len(matching_dirs)} directories matching pattern {config.base_dir_pattern}')

        # For each matching directory, collect files and create zip
        for basedir in matching_dirs:
            files_to_zip = []
            # Search for files matching patterns relative to basedir
            for file_pattern in config.patterns:
                for fps in glob.glob(os.path.join(str(basedir), file_pattern), recursive=True):
                    if os.path.isfile(fps):
                        files_to_zip.append(Path(fps))

            if not files_to_zip:
                logger.debug(f'No files found in {basedir} matching patterns {config.patterns}')
                continue

            # Create zip file in the basedir with name <artifact_type>.zip
            zip_path = basedir / f'{artifact_type}.zip'
            logger.debug(f'Creating zip {zip_path} with {len(files_to_zip)} files')

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Resolve basedir to absolute path to ensure relative_to() works correctly
                basedir_resolved = basedir.resolve()
                for fp in files_to_zip:
                    # Resolve filepath to absolute path before computing relative path
                    filepath_resolved = fp.resolve()
                    # Add file to zip with path relative to basedir
                    arcname = filepath_resolved.relative_to(basedir_resolved)
                    zipf.write(filepath_resolved, arcname)

            # Upload the zip file
            s3_path = self._get_s3_path(prefix, zip_path)
            tasks.append(lambda _zip_path=zip_path, _s3_path=s3_path: _upload_zip_task(_zip_path, _s3_path))

        execute_concurrent_tasks(tasks, task_name='uploading zip file')
        return len(tasks)

    def _download_files_from_presigned_json(
        self,
        presigned_json: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        with open(presigned_json) as f:
            presigned_urls = json.load(f)

        from_path_rel = from_path.relative_to(self.envs.IDF_PATH)
        patterns = self._get_patterns_for_type(artifact_type)
        if from_path_rel != Path('.'):
            patterns = [os.path.join(str(from_path_rel), pattern) for pattern in patterns]
        patterns_regexes = [re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns]

        def _download_task(_url: str, _output_path: Path) -> None:
            logger.debug(f'Downloading {_url} to {_output_path}')
            _output_path.parent.mkdir(parents=True, exist_ok=True)

            response = requests.get(_url, stream=True)
            if response.status_code != 200:
                raise PresignedUrlError(f'Failed to download {_output_path.name}: {response.status_code}')

            with open(_output_path, 'wb') as f:
                f.write(response.content)

        tasks = []
        for rel_path, url in presigned_urls.items():
            if not any(pattern.match(str(rel_path)) for pattern in patterns_regexes):
                continue

            output_path = Path(self.envs.IDF_PATH) / rel_path
            tasks.append(lambda _url=url, _output_path=output_path: _download_task(_url, _output_path))

        execute_concurrent_tasks(tasks, task_name='downloading object')
        return len(tasks)

    def _download_zip_from_presigned_json(
        self,
        presigned_json: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        """Download and extract zip files from presigned URLs."""
        with open(presigned_json) as f:
            presigned_urls = json.load(f)

        zip_filename = f'{artifact_type}.zip'
        from_path_rel = from_path.relative_to(self.envs.IDF_PATH)

        def _download_and_extract(url: str, output_path: Path) -> None:
            logger.debug(f'Downloading {url} to {output_path}')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            response = requests.get(url, stream=True)
            if response.status_code != 200:
                raise PresignedUrlError(f'Failed to download {output_path.name}: {response.status_code}')

            with open(output_path, 'wb') as f:
                f.write(response.content)

            self._extract_zip_file(output_path)

        tasks = []
        for rel_path, url in presigned_urls.items():
            rel_path_obj = Path(rel_path)
            if rel_path_obj.name != zip_filename:
                continue

            if from_path_rel != Path('.') and from_path_rel not in rel_path_obj.parents:
                continue

            output_path = Path(self.envs.IDF_PATH) / rel_path
            tasks.append(lambda u=url, op=output_path: _download_and_extract(u, op))

        execute_concurrent_tasks(tasks, task_name='downloading and extracting zip from presigned URLs')
        return len(tasks)

    def download_artifacts(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
        presigned_json: t.Optional[str] = None,
    ) -> None:
        """Download artifacts from S3 or via presigned URLs.

        When presigned_json is provided, downloads artifacts from presigned URLs.

        :param commit_sha: Optional commit SHA. If no commit_sha provided, will use

            1. PIPELINE_COMMIT_SHA env var
            2. latest commit from branch
        :param branch: Optional Git branch. If no branch provided, will use current
            branch
        :param artifact_type: Type of artifacts to download (debug, flash, metrics)
        :param folder: Download artifacts under this folder
        :param presigned_json: Path to the presigned.json file for download

        :raises ValueError: If S3 artifacts are not enabled
        """
        if not self.settings.gitlab.artifacts.s3.enable:
            raise ValueError('S3 artifacts are not enabled in the CI settings')

        params = ArtifactParams(
            commit_sha=commit_sha,
            branch=branch,
            folder=folder,
        )

        start_time = time.time()
        downloaded_count = 0

        if not presigned_json:
            # download from s3 directly
            logger.info(f'Downloading artifacts under {params.from_path} from s3 (commit sha: {params.commit_sha})')

            for art_type in self._get_artifact_types(artifact_type):
                config = self.settings.gitlab.artifacts.s3.configs[art_type]
                if config.zip_first:
                    downloaded_count += self._download_zip_from_s3(
                        prefix=f'{self.settings.gitlab.project}/{params.commit_sha}/',
                        from_path=params.from_path,
                        artifact_type=art_type,
                    )
                else:
                    downloaded_count += self._download_files_from_s3(
                        prefix=f'{self.settings.gitlab.project}/{params.commit_sha}/',
                        from_path=params.from_path,
                        artifact_type=art_type,
                    )
            logger.info(f'Downloaded {downloaded_count} artifacts in {time.time() - start_time:.2f} seconds')
            return

        # download from presigned urls
        logger.info(f'Downloading artifacts under {params.from_path} from presigned JSON')

        for art_type in self._get_artifact_types(artifact_type):
            config = self.settings.gitlab.artifacts.s3.configs[art_type]
            if config.zip_first:
                downloaded_count += self._download_zip_from_presigned_json(
                    presigned_json,
                    params.from_path,
                    art_type,
                )
            else:
                downloaded_count += self._download_files_from_presigned_json(
                    presigned_json,
                    params.from_path,
                    art_type,
                )
        logger.info(f'Downloaded {downloaded_count} artifacts in {time.time() - start_time:.2f} seconds')

    def upload_artifacts(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
    ) -> None:
        """Upload artifacts to S3.

        :param commit_sha: Optional commit SHA. If no commit_sha provided, will use 1)
            PIPELINE_COMMIT_SHA env var, 2) latest commit from branch
        :param branch: Optional Git branch. If no branch provided, will use current
            branch
        :param artifact_type: Type of artifacts to upload (debug, flash, metrics)
        :param folder: Upload artifacts under this folder

        :raises ValueError: If S3 artifacts are not enabled
        :raises S3Error: If S3 is not configured
        """
        if not self.settings.gitlab.artifacts.s3.enable:
            raise ValueError('S3 artifacts are not enabled in the CI settings')

        params = ArtifactParams(
            commit_sha=commit_sha,
            branch=branch,
            folder=folder,
        )

        if not self.s3_client:
            raise S3Error('Configure S3 storage to upload artifacts')

        prefix = f'{self.settings.gitlab.project}/{params.commit_sha}/'
        logger.info(f'Uploading artifacts under {params.from_path} to s3 (commit sha: {params.commit_sha})')

        start_time = time.time()
        uploaded_count = 0

        for art_type in self._get_artifact_types(artifact_type):
            config = self.settings.gitlab.artifacts.s3.configs[art_type]
            if config.zip_first:
                uploaded_count += self._upload_zip_to_s3(
                    prefix=prefix,
                    from_path=params.from_path,
                    artifact_type=art_type,
                )
            else:
                uploaded_count += self._upload_files_to_s3(
                    prefix=prefix,
                    from_path=params.from_path,
                    artifact_type=art_type,
                )

        logger.info(f'Uploaded {uploaded_count} artifacts in {time.time() - start_time:.2f} seconds')

    def generate_presigned_json(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
        expire_in_days: int = 4,
    ) -> t.Dict[str, str]:
        """Generate presigned URLs for artifacts in S3 storage.

        Generates presigned URLs for artifacts that would be uploaded to S3 storage. The
        URLs can be used to download the artifacts directly from S3.

        :param commit_sha: Optional commit SHA. If no commit_sha provided, will use 1)
            PIPELINE_COMMIT_SHA env var, 2) latest commit from branch
        :param branch: Optional Git branch. If no branch provided, will use current
            branch
        :param artifact_type: Type of artifacts to generate URLs for (debug, flash,
            metrics)
        :param folder: Base folder to generate relative paths from
        :param expire_in_days: Expiration time in days for the presigned URLs (default:
            4 days)

        :returns: Dictionary mapping relative paths to presigned URLs

        :raises S3Error: If S3 is not configured
        """
        params = ArtifactParams(
            commit_sha=commit_sha,
            branch=branch,
            folder=folder,
        )

        if not self.s3_client:
            raise S3Error('Configure S3 storage to generate presigned URLs')

        prefix = f'{self.settings.gitlab.project}/{params.commit_sha}/'
        s3_path = self._get_s3_path(prefix, params.from_path)

        def _get_presigned_url_task(_bucket: str, _obj_name: str) -> t.Tuple[str, str]:
            res = self.s3_client.get_presigned_url(  # type: ignore
                'GET',
                bucket_name=_bucket,
                object_name=_obj_name,
                expires=timedelta(days=expire_in_days),
            )
            if not res:
                raise S3Error(f'Failed to generate presigned URL for {_obj_name}')

            return _obj_name, res

        tasks = []
        presigned_urls: t.Dict[str, str] = {}
        bucket_zip_artifacts: t.Dict[str, t.Set[str]] = defaultdict(set)
        bucket_patterns: t.Dict[str, t.List[str]] = defaultdict(list)
        for art_type in self._get_artifact_types(artifact_type):
            config = self.settings.gitlab.artifacts.s3.configs[art_type]
            if config.zip_first:
                bucket_zip_artifacts[config.bucket].add(art_type)
            else:
                bucket_patterns[config.bucket].extend(self._get_patterns_for_type(art_type))

        for bucket, artifact_types in bucket_zip_artifacts.items():
            zip_filenames = {f'{art_type}.zip' for art_type in artifact_types}
            for obj in self.s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
                output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
                if output_path.name not in zip_filenames:
                    continue

                tasks.append(
                    lambda _bucket=bucket, _obj_name=obj.object_name: _get_presigned_url_task(_bucket, _obj_name)
                )

        for bucket, patterns in bucket_patterns.items():
            patterns_regexes = [
                re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns
            ]

            for obj in self.s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
                output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
                if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                    continue

                tasks.append(
                    lambda _bucket=bucket, _obj_name=obj.object_name: _get_presigned_url_task(_bucket, _obj_name)
                )

        results = execute_concurrent_tasks(tasks, task_name='generating presigned URL')
        for obj_name, presigned_url in results:
            presigned_urls[obj_name.replace(prefix, '')] = presigned_url

        return presigned_urls

    def _download_presigned_json_from_pipeline(
        self, pipeline_id: str, presigned_json_filename: str = 'presigned.json'
    ) -> str:
        """Download presigned.json file from a specific GitLab pipeline.

        Uses a local cache to avoid re-downloading the same presigned.json file for the
        same pipeline ID.

        :param pipeline_id: GitLab pipeline ID to download presigned.json from
        :param presigned_json_filename: Name of the presigned.json file to download

        :returns: Path to the presigned.json file (cached or downloaded)

        :raises ArtifactError: If presigned.json cannot be found or downloaded
        """
        if not self.settings.gitlab.build_pipeline.presigned_json_job_name:
            raise ArtifactError('Presigned JSON job name is not configured')

        # Check cache first
        cache_dir = Path(tempfile.gettempdir()) / '.cache' / 'idf-ci' / 'presigned_json' / pipeline_id
        cached_file = cache_dir / presigned_json_filename

        if cached_file.exists():
            logger.info(f'Using cached {presigned_json_filename} for pipeline {pipeline_id}')
            return str(cached_file)

        logger.info(f'Downloading {presigned_json_filename} from pipeline {pipeline_id}')

        # Find the child pipeline with the configured name
        child_pipeline_id = None
        try:
            for bridge in self.project.pipelines.get(pipeline_id, lazy=True).bridges.list(iterator=True):
                if bridge.name == self.settings.gitlab.build_pipeline.workflow_name:
                    child_pipeline_id = bridge.downstream_pipeline['id']
                    break
        except Exception as e:
            raise ArtifactError(f'Failed to get child pipeline from pipeline {pipeline_id}: {e}')

        if not child_pipeline_id:
            raise ArtifactError(
                f'No child pipeline found for pipeline {pipeline_id} with name '
                f'{self.settings.gitlab.build_pipeline.workflow_name}'
            )

        # Get the child pipeline and find the job that generates presigned.json
        download_from_job = None
        try:
            for job in self.project.pipelines.get(child_pipeline_id, lazy=True).jobs.list(iterator=True):
                if job.name == self.settings.gitlab.build_pipeline.presigned_json_job_name:
                    download_from_job = job
                    break
        except Exception as e:
            raise ArtifactError(
                f'Failed to get job {self.settings.gitlab.build_pipeline.presigned_json_job_name} '
                f'from child pipeline {child_pipeline_id}: {e}'
            )

        if not download_from_job:
            raise ArtifactError(
                f'No job found in child pipeline {child_pipeline_id} with name '
                f'{self.settings.gitlab.build_pipeline.presigned_json_job_name}'
            )

        # Download the presigned.json file from the job artifacts
        try:
            artifact_data = self.project.jobs.get(download_from_job.id, lazy=True).artifact(presigned_json_filename)
        except Exception as e:
            raise ArtifactError(
                f'Failed to get artifact {presigned_json_filename} from job {download_from_job.id}: {e}'
            )

        # Create cache directory and save to cache
        cache_dir.mkdir(parents=True, exist_ok=True)
        with open(cached_file, 'wb') as fw:
            fw.write(artifact_data)

        logger.debug(f'Successfully downloaded and cached {presigned_json_filename} for pipeline {pipeline_id}')
        return str(cached_file)
