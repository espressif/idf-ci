# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import glob
import logging
import os
import re
import typing as t
from pathlib import Path

import minio
import urllib3

from .._vendor import translate
from ..envs import GitlabEnvVars

logger = logging.getLogger(__name__)


def create_s3_client() -> t.Optional[minio.Minio]:
    """Create and configure an S3 client if all required credentials are available.

    :returns: Configured Minio client instance if all credentials are available, None
        otherwise
    """
    env = GitlabEnvVars()
    if not all(
        [
            env.IDF_S3_SERVER,
            env.IDF_S3_ACCESS_KEY,
            env.IDF_S3_SECRET_KEY,
        ]
    ):
        logger.info('S3 credentials not available. Skipping S3 features...')
        return None

    if env.IDF_S3_SERVER.startswith('https://'):  # type: ignore
        host = env.IDF_S3_SERVER.replace('https://', '')  # type: ignore
        secure = True
    elif env.IDF_S3_SERVER.startswith('http://'):  # type: ignore
        host = env.IDF_S3_SERVER.replace('http://', '')  # type: ignore
        secure = False
    else:
        raise ValueError('Please provide a http or https server URL for S3')

    return minio.Minio(
        host,
        access_key=env.IDF_S3_ACCESS_KEY,
        secret_key=env.IDF_S3_SECRET_KEY,
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


def download_from_s3(
    s3_client: minio.Minio,
    *,
    bucket: str,
    s3_prefix: str,
    rel_to_idf: str,
    patterns: t.List[str],
) -> None:
    """Download artifacts from S3 storage and place them in-place relative to IDF_PATH.

    :param s3_client: Configured Minio client instance
    :param bucket: S3 bucket name
    :param s3_prefix: Prefix to use for S3 object names
    :param rel_to_idf: Input directory path
    :param patterns: List of glob patterns to match files against
    """
    env = GitlabEnvVars()

    if rel_to_idf == '.':
        s3_folder = s3_prefix
    else:
        s3_folder = f'{s3_prefix}{rel_to_idf}'
    logger.info(f'Downloading objects from s3 under {s3_folder}')

    patterns_regexes = [re.compile(translate(pattern, recursive=True, include_hidden=True)) for pattern in patterns]

    for obj in s3_client.list_objects(
        bucket,
        prefix=s3_folder,
        recursive=True,
    ):
        try:
            output_path = Path(env.IDF_PATH) / obj.object_name.replace(s3_prefix, '')

            if not any(pattern.match(str(output_path)) for pattern in patterns_regexes):
                continue

            logger.debug(f'Downloading {obj.object_name} to {output_path}')
            s3_client.fget_object(bucket, obj.object_name, str(output_path))
        except minio.error.S3Error as e:
            logger.error(f'Error downloading from S3: {e}')
            raise


def upload_to_s3(
    s3_client: minio.Minio,
    *,
    bucket: str,
    prefix: str,
    from_path: Path,
    patterns: t.List[str],
) -> None:
    """Upload files to S3 storage that match the given patterns.

    :param s3_client: Configured Minio client instance
    :param bucket: S3 bucket name
    :param prefix: Prefix to use for S3 object names
    :param from_path: upload directory path
    :param patterns: List of patterns to match files against
    """
    env = GitlabEnvVars()
    logger.debug(f'Uploading objects to S3 bucket {bucket} with prefix {prefix}')

    # Use glob to find all matching files recursively
    for pattern in patterns:
        # Convert pattern to absolute path pattern
        abs_pattern = os.path.join(str(from_path), pattern)
        for file_str in glob.glob(abs_pattern, recursive=True):
            file_path = Path(file_str)
            if not file_path.is_file():
                continue

            # Upload the file
            rel_path = str(file_path.relative_to(env.IDF_PATH))
            s3_path = f'{prefix}{rel_path}'
            logger.debug(f'Uploading {file_path} to {s3_path}')

            try:
                s3_client.fput_object(
                    bucket,
                    s3_path,
                    str(file_path),
                )
            except minio.error.S3Error as e:
                logger.error(f'Error uploading to S3: {e}')
                raise
