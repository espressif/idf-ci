# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import typing as t

from pydantic_settings import (
    BaseSettings,
)

from idf_ci._compat import UNDEF, UndefinedOr, is_defined_and_satisfies

logger = logging.getLogger(__name__)


class GitlabEnvVars(BaseSettings):
    """GitLab environment variables.

    This class defines all GitLab-specific environment variables that can be set via GitLab CI/CD variables
    or secrets. These variables are used for GitLab API authentication and pipeline configuration.

    Pipeline Control Variables:
    - CHANGED_FILES_SEMICOLON_SEPARATED: List of changed files in semicolon-separated format
    - IS_FULL_TEST_PIPELINE: Whether to run a full test pipeline
    - IS_MR_PIPELINE: Whether this is a merge request pipeline
    - IS_DEBUG_PIPELINE: Whether this is a debug pipeline
    - DYNAMIC_PIPELINE_FILTER_EXPR: Expression for filtering pipeline jobs

    GitLab API Authentication:
    - GITLAB_HTTPS_SERVER: GitLab server URL (default: https://gitlab.com)
    - GITLAB_ACCESS_TOKEN: GitLab API access token

    S3 Storage Configuration:
    - IDF_S3_SERVER: S3 server URL
    - IDF_S3_BUCKET: S3 bucket name
    - IDF_S3_ACCESS_KEY: S3 access key
    - IDF_S3_SECRET_KEY: S3 secret key
    """

    # Pipeline Control Variables
    CHANGED_FILES_SEMICOLON_SEPARATED: UndefinedOr[str] = UNDEF

    IS_FULL_TEST_PIPELINE: UndefinedOr[bool] = UNDEF
    IS_MR_PIPELINE: UndefinedOr[bool] = UNDEF
    IS_DEBUG_PIPELINE: UndefinedOr[bool] = UNDEF

    DYNAMIC_PIPELINE_FILTER_EXPR: UndefinedOr[str] = UNDEF

    # GitLab API Authentication
    GITLAB_HTTPS_SERVER: str = 'https://gitlab.com'
    GITLAB_ACCESS_TOKEN: t.Optional[str] = None

    # S3 Storage Configuration
    IDF_S3_BUCKET: str = 'idf-artifacts'
    IDF_S3_SERVER: t.Optional[str] = None
    IDF_S3_ACCESS_KEY: t.Optional[str] = None
    IDF_S3_SECRET_KEY: t.Optional[str] = None

    # other env vars used
    IDF_PATH: str = ''

    @property
    def is_full_pipeline(self) -> bool:
        """Determine if this is a full pipeline run.

        A full pipeline run is determined by:
        1. IS_FULL_TEST_PIPELINE is set to "1"
        2. IS_MR_PIPELINE is set to "0"

        :return: True if this is a full pipeline run, False otherwise
        """
        if is_defined_and_satisfies(self.IS_FULL_TEST_PIPELINE, lambda x: x == '1'):
            logger.info('Running in full pipeline mode since IS_FULL_TEST_PIPELINE is set to "1"')
            return True

        if is_defined_and_satisfies(self.IS_MR_PIPELINE, lambda x: x == '0'):
            logger.info('Running in full pipeline mode since IS_MR_PIPELINE is set to "0"')
            return True

        return False
