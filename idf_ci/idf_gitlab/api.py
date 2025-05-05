# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import glob
import json
import logging
import os
import re
import typing as t
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

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


@dataclass
class ArtifactParams:
    """Common parameters for artifact operations."""

    commit_sha: t.Optional[str] = None
    artifact_type: t.Optional[str] = None
    folder: t.Optional[str] = None
    presigned_json: t.Optional[str] = None
    expire_in_days: int = 4

    def __post_init__(self):
        if self.folder is None:
            self.folder = os.getcwd()
        self.from_path = Path(self.folder)


class ArtifactError(Exception):
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

    def _get_commit_sha(self, commit_sha: t.Optional[str], branch: t.Optional[str]) -> str:
        if commit_sha:
            return commit_sha

        if branch is None:
            branch = get_current_branch()
            logger.debug(f'Using current branch: {branch}')
        else:
            logger.debug(f'Using specified branch: {branch}')

        mrs = self.project.mergerequests.list(state='opened', source_branch=branch)
        if not mrs:
            raise ValueError(f'No open merge request found for branch {branch}')
        return next(mrs[0].commits()).id

    def _get_upload_details_by_type(self, artifact_type: t.Optional[str]) -> t.Dict[str, t.List[str]]:
        """Get file patterns grouped by bucket name based on the artifact type.

        :param artifact_type: Type of artifacts to download (debug, flash, metrics)

        :returns: Dictionary mapping bucket names to lists of patterns

        :raises ValueError: If the artifact type is invalid
        """
        if artifact_type:
            if artifact_type not in self.settings.gitlab.artifacts.available_s3_types:
                raise ValueError(
                    f'Invalid artifact type: {artifact_type}. '
                    f'Available types: {self.settings.gitlab.artifacts.available_s3_types}'
                )
            config = self.settings.gitlab.artifacts.s3[artifact_type]
            return {config['bucket']: config['patterns']}
        else:
            # If no type specified, return all configurations grouped by bucket
            bucket_patterns: t.Dict[str, t.List[str]] = {}
            for config in self.settings.gitlab.artifacts.s3.values():
                bucket = config['bucket']
                if bucket not in bucket_patterns:
                    bucket_patterns[bucket] = []
                bucket_patterns[bucket].extend(config['patterns'])

            if not bucket_patterns:
                raise ValueError('No S3 buckets configured')
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
        rel_path = str(from_path.relative_to(self.envs.IDF_PATH))
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

        for obj in s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
            output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
            if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                continue

            logger.debug(f'Downloading {obj.object_name} to {output_path}')
            s3_client.fget_object(bucket, obj.object_name, str(output_path))

    def _upload_to_s3(
        self,
        s3_client: minio.Minio,
        *,
        bucket: str,
        prefix: str,
        from_path: Path,
        patterns: t.List[str],
    ) -> None:
        for pattern in patterns:
            abs_pattern = os.path.join(str(from_path), pattern)
            for file_str in glob.glob(abs_pattern, recursive=True):
                file_path = Path(file_str)
                if not file_path.is_file():
                    continue

                s3_path = self._get_s3_path(prefix, file_path)
                logger.debug(f'Uploading {file_path} to {s3_path}')
                s3_client.fput_object(bucket, s3_path, str(file_path))

    def _download_from_presigned_json(self, presigned_json: str, from_path: Path, patterns: t.List[str]) -> None:
        with open(presigned_json) as f:
            presigned_urls = json.load(f)

        patterns_regexes = [re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns]

        for rel_path, url in presigned_urls.items():
            output_path = from_path / rel_path
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

        There are two main use cases:

        1. CI use case: Use commit_sha to download artifacts from a specific commit
        2. Local use case: Use branch to download artifacts from the latest pipeline of
           a branch

        :param commit_sha: Optional commit SHA. If provided, will download from this
            specific commit
        :param branch: Optional Git branch. If no commit_sha provided, will use current
            branch
        :param artifact_type: Type of artifacts to download (debug, flash, metrics)
        :param folder: download artifacts under this folder
        :param presigned_json: Path to the presigned.json file. If provided, will use
            this file to download artifacts. If not, will use s3 credentials to download
        """
        params = ArtifactParams(
            commit_sha=commit_sha,
            artifact_type=artifact_type,
            folder=folder,
            presigned_json=presigned_json,
        )

        commit_sha = self._get_commit_sha(commit_sha, branch)

        if presigned_json:
            self._download_from_presigned_json(
                presigned_json,
                params.from_path,
                [p for patterns in self._get_upload_details_by_type(artifact_type).values() for p in patterns],
            )
            return

        s3_client = self.s3_client
        if not s3_client:
            raise S3Error('Configure S3 storage to download artifacts')

        s3_prefix = f'{self.settings.gitlab.project}/{commit_sha}/'
        logger.info(f'Downloading artifacts under {params.from_path} from s3 (commit sha: {commit_sha})')

        for bucket, patterns in self._get_upload_details_by_type(artifact_type).items():
            self._download_from_s3(
                s3_client=s3_client,
                bucket=bucket,
                prefix=s3_prefix,
                from_path=params.from_path,
                patterns=patterns,
            )

    def upload_artifacts(
        self,
        *,
        commit_sha: str,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
    ) -> None:
        """Upload artifacts to S3 storage.

        This method uploads artifacts to S3 storage only. GitLab's built-in storage is
        not supported. The commit SHA is required to identify where to store the
        artifacts.

        :param commit_sha: Commit SHA to upload artifacts to
        :param artifact_type: Type of artifacts to upload (debug, flash, metrics)
        :param folder: upload artifacts under this folder

        :raises S3Error: If S3 is not configured
        """
        params = ArtifactParams(
            commit_sha=commit_sha,
            artifact_type=artifact_type,
            folder=folder,
        )

        if not commit_sha:
            raise ValueError('Commit SHA is required to upload artifacts')

        s3_client = self.s3_client
        if not s3_client:
            raise S3Error('Configure S3 storage to upload artifacts')

        prefix = f'{self.settings.gitlab.project}/{commit_sha}/'
        logger.info(f'Uploading artifacts under {params.from_path} to s3 (commit sha: {commit_sha})')

        for bucket, patterns in self._get_upload_details_by_type(artifact_type).items():
            self._upload_to_s3(
                s3_client=s3_client,
                bucket=bucket,
                prefix=prefix,
                from_path=params.from_path,
                patterns=patterns,
            )

    def generate_presigned_json(
        self,
        *,
        commit_sha: str,
        artifact_type: t.Optional[str] = None,
        folder: t.Optional[str] = None,
        expire_in_days: int = 4,
    ) -> t.Dict[str, str]:
        """Generate presigned URLs for artifacts in S3 storage.

        This method generates presigned URLs for artifacts that would be uploaded to S3
        storage. The URLs can be used to download the artifacts directly from S3.

        :param commit_sha: Commit SHA to generate presigned URLs for
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
            artifact_type=artifact_type,
            folder=folder,
            expire_in_days=expire_in_days,
        )

        if not commit_sha:
            raise ValueError('Commit SHA is required to generate presigned URLs')

        s3_client = self.s3_client
        if not s3_client:
            raise S3Error('Configure S3 storage to generate presigned URLs')

        prefix = f'{self.settings.gitlab.project}/{commit_sha}/'
        s3_path = self._get_s3_path(prefix, params.from_path)

        presigned_urls: t.Dict[str, str] = {}
        for bucket, patterns in self._get_upload_details_by_type(artifact_type).items():
            patterns_regexes = [
                re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns
            ]

            for obj in s3_client.list_objects(bucket, prefix=s3_path, recursive=True):
                output_path = Path(self.envs.IDF_PATH) / obj.object_name.replace(prefix, '')
                rel_path = obj.object_name.replace(prefix, '')

                if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                    continue

                presigned_url = s3_client.get_presigned_url(
                    'GET',
                    bucket_name=bucket,
                    object_name=obj.object_name,
                    expires=timedelta(days=expire_in_days),
                )
                presigned_urls[rel_path] = presigned_url

        return presigned_urls
