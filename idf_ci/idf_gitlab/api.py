# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import glob
import json
import logging
import os
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
from ..envs import GitlabEnvVars
from ..settings import get_ci_settings
from ..utils import get_current_branch

logger = logging.getLogger(__name__)


def execute_concurrent_tasks(
    tasks: t.List[t.Callable[..., t.Any]],
    max_workers: t.Optional[int] = None,
    task_name: str = 'executing task',
) -> t.List[t.Any]:
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


class S3ArtifactManager:
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

    def _create_s3_client(self) -> t.Optional[minio.Minio]:
        if not self.envs.IDF_S3_SERVER:
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
            access_key=self.envs.IDF_S3_ACCESS_KEY,
            secret_key=self.envs.IDF_S3_SECRET_KEY,
            secure=secure,
            http_client=urllib3.PoolManager(
                num_pools=10,
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

    def _get_artifact_types(self, artifact_type: t.Optional[str]) -> t.List[str]:
        if artifact_type and artifact_type not in self.settings.gitlab.artifacts.s3.configs:
            raise ValueError(
                f'Invalid artifact type: {artifact_type}. '
                f'Available types: {list(self.settings.gitlab.artifacts.s3.configs.keys())}'
            )

        available_types = []
        for art_type, config in self.settings.gitlab.artifacts.s3.configs.items():
            # Check if_clause condition
            if config.get('if_clause'):
                try:
                    stmt = esp_bool_parser.parse_bool_expr(config['if_clause'])
                    res = stmt.get_value('', '')
                except Exception as e:
                    logger.info(
                        f'Skipping {artifact_type} artifacts due to error '
                        f'while evaluating if_clause: {config["if_clause"]}:\n'
                        f'{e}'
                    )
                    continue

                if res:
                    available_types.append(art_type)
                else:
                    logger.debug(f'Skipping {artifact_type} artifacts due to if_clause: {config["if_clause"]}')
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

    def _upload_zip_to_s3(
        self,
        s3_client: minio.Minio,
        *,
        bucket: str,
        prefix: str,
        from_path: Path,
        artifact_type: str,
    ) -> int:
        """Upload artifacts as zip files to S3.

        This method:

        1. Finds directories matching ``base_dir_pattern`` (only folders).
        2. For each directory, finds files matching ``file_patterns`` (relative to that
           directory).
        3. Creates a zip file named ``<artifact_type>.zip`` in that directory.
        4. Uploads the zip file to S3.

        :param s3_client: S3 client instance
        :param bucket: S3 bucket name
        :param prefix: S3 prefix path
        :param from_path: Base path to search from
        :param artifact_type: Type of artifact (used as zip filename)

        :returns: Number of zip files uploaded
        """
        zip_config = self.settings.gitlab.artifacts.s3.configs[artifact_type]
        base_dir_pattern = zip_config.get('base_dir_pattern')
        file_patterns = zip_config.get('file_patterns') or ['**/*']

        def _upload_zip_task(_zip_path: Path, _s3_path: str) -> None:
            logger.debug(f'Uploading zip {_zip_path} to {_s3_path}')
            s3_client.fput_object(bucket, _s3_path, str(_zip_path))

        tasks = []
        # Find all directories matching base_dir_pattern
        # The pattern should match directories only (e.g., '**/build*/')
        if not base_dir_pattern:
            matching_dirs = [from_path.resolve()]
        else:
            pattern_path = Path(from_path) / base_dir_pattern
            abs_pattern = os.path.realpath(str(pattern_path))
            # Remove trailing slash if present for glob matching
            # Pattern like '**/build*/' should match directories starting with 'build'
            pattern_for_glob = abs_pattern.rstrip('/')

            # Use glob to find all matches, then filter for directories only
            matching_dirs = [
                Path(match).resolve() for match in glob.glob(pattern_for_glob, recursive=True) if Path(match).is_dir()
            ]

        logger.debug(f'Found {len(matching_dirs)} directories matching pattern {base_dir_pattern}')

        # For each matching directory, collect files and create zip
        for basedir in matching_dirs:
            files_to_zip = []
            # Search for files matching file_patterns relative to basedir
            for file_pattern in file_patterns:
                for fps in glob.glob(os.path.join(str(basedir), file_pattern), recursive=True):
                    if os.path.isfile(fps):
                        files_to_zip.append(Path(fps))

            if not files_to_zip:
                logger.debug(f'No files found in {basedir} matching patterns {file_patterns}')
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
        bucket: str,
        prefix: str,
        from_path: Path,
        artifact_types: t.Set[str],
    ) -> int:
        """Download and extract zip files from S3."""
        if not self.s3_client:
            raise S3Error('S3 client is not configured, please configure S3 credentials')

        s3_path = self._get_s3_path(prefix, from_path)
        zip_filenames = {f'{art_type}.zip' for art_type in artifact_types}

        def _download_and_extract(obj_name: str, zip_path: Path) -> None:
            logger.debug(f'Downloading {obj_name} to {zip_path}')
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            self.s3_client.fget_object(bucket, obj_name, str(zip_path))  # type: ignore
            self._extract_zip_file(zip_path)

        # Find matching zip files
        tasks = []
        for obj in self.s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
            output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
            if output_path.name in zip_filenames:
                tasks.append(lambda o=obj.object_name, op=output_path: _download_and_extract(o, op))

        execute_concurrent_tasks(tasks, task_name='downloading and extracting zip from S3')
        return len(tasks)

    def _download_zip_from_presigned_json(
        self,
        presigned_json: str,
        from_path: Path,
        artifact_types: t.Set[str],
    ) -> int:
        """Download and extract zip files from presigned URLs."""
        with open(presigned_json) as f:
            presigned_urls = json.load(f)

        zip_filenames = {f'{art_type}.zip' for art_type in artifact_types}

        def _download_and_extract(url: str, output_path: Path) -> None:
            logger.debug(f'Downloading {url} to {output_path}')
            output_path.parent.mkdir(parents=True, exist_ok=True)

            response = requests.get(url, stream=True)
            if response.status_code != 200:
                raise PresignedUrlError(f'Failed to download {output_path.name}: {response.status_code}')

            with open(output_path, 'wb') as f:
                f.write(response.content)

            self._extract_zip_file(output_path)

        # Filter URLs that match our criteria
        tasks = []
        for rel_path, url in presigned_urls.items():
            rel_path_obj = Path(rel_path)
            if rel_path_obj.name not in zip_filenames:
                continue

            # Simple path check - if from_path is specified, only download files under it
            if from_path != Path('.') and from_path not in rel_path_obj.parents:
                continue

            output_path = Path(self.envs.IDF_PATH) / rel_path
            tasks.append(lambda u=url, op=output_path: _download_and_extract(u, op))

        execute_concurrent_tasks(tasks, task_name='downloading and extracting zip from presigned URLs')
        return len(tasks)

    def download_s3_artifacts(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
        presigned_json: t.Optional[str] = None,
        pipeline_id: t.Optional[str] = None,
    ) -> None:
        """Download zip artifacts from S3 or via presigned URLs.

        Downloads zip files from S3 when credentials are available. If S3 access fails,
        and presigned JSON is available (via ``presigned_json`` or ``pipeline_id``),
        falls back to downloading zip artifacts from presigned URLs.

        :param commit_sha: Optional commit SHA. If no commit_sha provided, will use 1)
            PIPELINE_COMMIT_SHA env var, 2) latest commit from branch
        :param branch: Optional Git branch. If no branch provided, will use current
            branch
        :param artifact_type: Type of artifacts to download (debug, flash, metrics)
        :param folder: Download artifacts under this folder
        :param presigned_json: Path to the presigned.json file for download
        :param pipeline_id: GitLab pipeline ID to download presigned.json from

        :raises ValueError: If S3 artifacts are not enabled
        """
        if not self.settings.gitlab.artifacts.s3.enable:
            raise ValueError('S3 artifacts are not enabled in the CI settings')

        if presigned_json and pipeline_id:
            raise ValueError('Cannot use both --presigned-json and --pipeline-id options together')

        params = ArtifactParams(
            commit_sha=commit_sha,
            branch=branch,
            folder=folder,
        )

        try:
            # download with s3 first, if not working, fall back to presigned json
            logger.info(f'Downloading artifacts under {params.from_path} from s3 (commit sha: {params.commit_sha})')

            start_time = time.time()
            downloaded_count = 0
            # Group artifact types by bucket
            bucket_artifact_types: t.Dict[str, t.Set[str]] = defaultdict(set)
            for art_type in self._get_artifact_types(artifact_type):
                config = self.settings.gitlab.artifacts.s3.configs[art_type]
                bucket_artifact_types[config['bucket']].add(art_type)

            for bucket, artifact_types in bucket_artifact_types.items():
                downloaded_count += self._download_zip_from_s3(
                    bucket=bucket,
                    prefix=f'{self.settings.gitlab.project}/{params.commit_sha}/',
                    from_path=params.from_path,
                    artifact_types=artifact_types,
                )
            logger.info(
                f'Downloaded and extracted {downloaded_count} zip files in {time.time() - start_time:.2f} seconds'
            )
            return
        except Exception as e:
            if self.settings.gitlab.build_pipeline.presigned_json_job_name:
                logger.warning(f'Failed to download artifacts from S3: {e}. Falling back to presigned URLs...')
            else:
                raise ArtifactError(f'Failed to download artifacts from S3: {e}.')

        if pipeline_id:
            presigned_json_path = self._download_presigned_json_from_pipeline(pipeline_id)
        elif presigned_json and os.path.isfile(presigned_json):
            presigned_json_path = presigned_json
        else:
            raise ArtifactError(
                'Either presigned_json or pipeline_id must be provided to download artifacts, if S3 is not configured'
            )

        logger.info(f'Downloading artifacts under {params.from_path} from pipeline {pipeline_id}')

        start_time = time.time()
        artifact_types = set(self._get_artifact_types(artifact_type))
        downloaded_files = self._download_zip_from_presigned_json(
            presigned_json_path,
            params.from_path,
            artifact_types,
        )
        logger.info(f'Downloaded and extracted {downloaded_files} zip files in {time.time() - start_time:.2f} seconds')

    def upload_s3_artifacts(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
    ) -> None:
        """Upload artifacts to S3 as zip files.

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
            uploaded_count += self._upload_zip_to_s3(
                s3_client=self.s3_client,
                bucket=config['bucket'],
                prefix=prefix,
                from_path=params.from_path,
                artifact_type=art_type,
            )

        logger.info(f'Uploaded {uploaded_count} zip files in {time.time() - start_time:.2f} seconds')

    def generate_presigned_json(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
        expire_in_days: int = 4,
    ) -> t.Dict[str, str]:
        """Generate presigned URLs for zip artifacts in S3 storage.

        Generates presigned URLs for zip files that would be uploaded to S3 storage. The
        URLs can be used to download the zip artifacts directly from S3.

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
        # Group artifact types by bucket
        bucket_artifact_types: t.Dict[str, t.Set[str]] = defaultdict(set)
        for art_type in self._get_artifact_types(artifact_type):
            config = self.settings.gitlab.artifacts.s3.configs[art_type]
            bucket_artifact_types[config['bucket']].add(art_type)

        for bucket, artifact_types in bucket_artifact_types.items():
            zip_filenames = {f'{art_type}.zip' for art_type in artifact_types}
            for obj in self.s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
                output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
                if output_path.name not in zip_filenames:
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
