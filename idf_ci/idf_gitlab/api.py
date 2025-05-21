# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import glob
import json
import logging
import os
import re
import subprocess
import typing as t
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
from ..settings import CiSettings
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

    :returns: List of successful task results, sequence is not guaranteed
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
    """Tool interface for managing artifacts in GitLab pipelines.

    This class provides a unified interface for downloading and uploading artifacts,
    supporting both GitLab's built-in storage and S3 storage. It handles:

    1. GitLab API operations (pipeline, merge request queries)
    2. S3 storage operations (artifact upload/download)
    3. Fallback to GitLab storage when S3 is not configured

    :var envs: GitLab environment variables
    :var settings: CI settings
    """

    def __init__(self):
        self.envs = GitlabEnvVars()
        self.settings = CiSettings()

        self._s3_client: t.Optional[Minio] = UNDEF  # type: ignore

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
        """Lazily initialize and cache the GitLab project."""
        project = self.gl.projects.get(self.settings.gitlab.project)
        if not project:
            raise ValueError(f'Project {self.settings.gitlab.project} not found')
        return project

    def _get_upload_details_by_type(self, artifact_type: t.Optional[str]) -> t.Dict[str, t.List[str]]:
        """Get file patterns grouped by bucket name based on the artifact type.

        :param artifact_type: Type of artifacts to download (debug, flash, metrics)

        :returns: Dictionary mapping bucket names to lists of patterns

        :raises ValueError: If the artifact type is invalid
        """
        _types = []
        if artifact_type:
            if artifact_type not in self.settings.gitlab.artifacts.available_s3_types:
                raise ValueError(
                    f'Invalid artifact type: {artifact_type}. '
                    f'Available types: {self.settings.gitlab.artifacts.available_s3_types}'
                )

            _types = [artifact_type]
        else:
            _types = self.settings.gitlab.artifacts.available_s3_types

        bucket_patterns: t.Dict[str, t.List[str]] = {}
        for artifact_type in _types:
            config = self.settings.gitlab.artifacts.s3[artifact_type]

            if config.get('if_clause'):
                try:
                    stmt = esp_bool_parser.parse_bool_expr(config['if_clause'])
                    res = stmt.get_value('', '')
                except Exception as e:
                    logger.info(
                        f'Skipping {artifact_type} artifacts due to error '
                        f'while evaluating if_clause: {config["if_clause"]}: {e}'
                    )
                    continue
                else:
                    if not res:
                        logger.info(f'Skipping {artifact_type} artifacts due to if_clause: {config["if_clause"]}')
                        continue

            bucket = config['bucket']
            if bucket not in bucket_patterns:
                bucket_patterns[bucket] = []
            bucket_patterns[bucket].extend(config['patterns'])

        if not bucket_patterns:
            logger.info('No S3 configured patterns found, skipping...')

        return bucket_patterns

    @property
    def s3_client(self) -> t.Optional[minio.Minio]:
        """Get or create the S3 client."""
        if is_undefined(self._s3_client):
            self._s3_client = self._create_s3_client()
        return self._s3_client

    def _create_s3_client(self) -> t.Optional[minio.Minio]:
        if not all(
            [
                self.envs.IDF_S3_SERVER,
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

        return minio.Minio(
            host,
            access_key=self.envs.IDF_S3_ACCESS_KEY,
            secret_key=self.envs.IDF_S3_SECRET_KEY,
            secure=secure,
            http_client=urllib3.PoolManager(
                num_pools=10,
                timeout=urllib3.Timeout.DEFAULT_TIMEOUT,
                retries=urllib3.Retry(
                    total=5,
                    backoff_factor=0.2,
                    status_forcelist=[500, 502, 503, 504],
                ),
            ),
        )

    def _get_s3_path(self, prefix: str, from_path: Path) -> str:
        if from_path.is_absolute():
            rel_path = str(from_path.relative_to(self.envs.IDF_PATH))
        else:
            rel_path = str(from_path)

        return f'{prefix}{rel_path}' if rel_path != '.' else prefix

    def _download_from_s3(
        self,
        s3_client: minio.Minio,
        *,
        bucket: str,
        prefix: str,
        from_path: Path,
        patterns: t.List[str],
    ) -> None:
        s3_path = self._get_s3_path(prefix, from_path)
        patterns_regexes = [re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns]

        def _download_task(_obj_name: str, _output_path: Path) -> None:
            logger.debug(f'Downloading {_obj_name} to {_output_path}')
            s3_client.fget_object(bucket, _obj_name, str(_output_path))

        tasks = []
        for obj in s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
            output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
            if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                continue
            tasks.append(
                lambda _obj_name=obj.object_name, _output_path=output_path: _download_task(_obj_name, _output_path)
            )

        execute_concurrent_tasks(tasks, task_name='downloading object')

    def _upload_to_s3(
        self,
        s3_client: minio.Minio,
        *,
        bucket: str,
        prefix: str,
        from_path: Path,
        patterns: t.List[str],
    ) -> None:
        def _upload_task(_filepath: Path, _s3_path: str) -> None:
            logger.debug(f'Uploading {_filepath} to {_s3_path}')
            s3_client.fput_object(bucket, _s3_path, str(_filepath))

        tasks = []
        for pattern in patterns:
            abs_pattern = os.path.join(str(from_path), pattern)
            for file_str in glob.glob(abs_pattern, recursive=True):
                filepath = Path(file_str)
                if not filepath.is_file():
                    continue

                s3_path = self._get_s3_path(prefix, filepath)
                tasks.append(lambda _filepath=filepath, _s3_path=s3_path: _upload_task(_filepath, _s3_path))

        execute_concurrent_tasks(tasks, task_name='uploading file')

    def _download_from_presigned_json(self, presigned_json: str, from_path: Path, patterns: t.List[str]) -> None:
        with open(presigned_json) as f:
            presigned_urls = json.load(f)

        patterns_regexes = [re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns]

        for rel_path, url in presigned_urls.items():
            if from_path not in Path(rel_path).parents:
                continue

            output_path = Path(self.envs.IDF_PATH) / rel_path
            if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                continue

            output_path.parent.mkdir(parents=True, exist_ok=True)

            response = requests.get(url, stream=True)
            if response.status_code != 200:
                raise PresignedUrlError(f'Failed to download {rel_path}: {response.status_code}')

            with open(output_path, 'wb') as f:
                f.write(response.content)
            logger.debug(f'Downloaded {rel_path} to {output_path}')

    def download_artifacts(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
        presigned_json: t.Optional[str] = None,
    ) -> None:
        """Download artifacts from a pipeline.

        This method downloads artifacts from either GitLab's built-in storage or S3
        storage, depending on the configuration and artifact type.

        :param commit_sha: Optional commit SHA. If no commit_sha provided, will use 1)
            PIPELINE_COMMIT_SHA env var, 2) latest commit from branch
        :param branch: Optional Git branch. If no branch provided, will use current
            branch
        :param artifact_type: Type of artifacts to download (debug, flash, metrics)
        :param folder: download artifacts under this folder
        :param presigned_json: Path to the presigned.json file. If provided, will use
            this file to download artifacts. If not, will use s3 credentials to download
        """
        params = ArtifactParams(
            commit_sha=commit_sha,
            branch=branch,
            folder=folder,
        )

        if presigned_json:
            self._download_from_presigned_json(
                presigned_json,
                params.from_path,
                [p for patterns in self._get_upload_details_by_type(artifact_type).values() for p in patterns],
            )
            return

        if not self.s3_client:
            raise S3Error('Configure S3 storage to download artifacts')

        s3_prefix = f'{self.settings.gitlab.project}/{params.commit_sha}/'
        logger.info(f'Downloading artifacts under {params.from_path} from s3 (commit sha: {params.commit_sha})')

        for bucket, patterns in self._get_upload_details_by_type(artifact_type).items():
            self._download_from_s3(
                s3_client=self.s3_client,
                bucket=bucket,
                prefix=s3_prefix,
                from_path=params.from_path,
                patterns=patterns,
            )

    def upload_artifacts(
        self,
        *,
        commit_sha: t.Optional[str] = None,
        branch: t.Optional[str] = None,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
    ) -> None:
        """Upload artifacts to S3 storage.

        This method uploads artifacts to S3 storage only. GitLab's built-in storage is
        not supported. The commit SHA is required to identify where to store the
        artifacts.

        :param commit_sha: Optional commit SHA. If no commit_sha provided, will use 1)
            PIPELINE_COMMIT_SHA env var, 2) latest commit from branch
        :param branch: Optional Git branch. If no branch provided, will use current
            branch
        :param artifact_type: Type of artifacts to upload (debug, flash, metrics)
        :param folder: upload artifacts under this folder

        :raises S3Error: If S3 is not configured
        """
        params = ArtifactParams(
            commit_sha=commit_sha,
            branch=branch,
            folder=folder,
        )

        if not self.s3_client:
            raise S3Error('Configure S3 storage to upload artifacts')

        prefix = f'{self.settings.gitlab.project}/{params.commit_sha}/'
        logger.info(f'Uploading artifacts under {params.from_path} to s3 (commit sha: {params.commit_sha})')

        for bucket, patterns in self._get_upload_details_by_type(artifact_type).items():
            self._upload_to_s3(
                s3_client=self.s3_client,
                bucket=bucket,
                prefix=prefix,
                from_path=params.from_path,
                patterns=patterns,
            )

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

        This method generates presigned URLs for artifacts that would be uploaded to S3
        storage. The URLs can be used to download the artifacts directly from S3.

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
        for bucket, patterns in self._get_upload_details_by_type(artifact_type).items():
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
