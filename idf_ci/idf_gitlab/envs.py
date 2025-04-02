# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import typing as t

from pydantic_settings import (
    BaseSettings,
)

logger = logging.getLogger(__name__)


class GitlabEnvVars(BaseSettings):
    # Pipeline Control Variables
    CHANGED_FILES_SEMICOLON_SEPARATED: t.Optional[str] = None

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

    # Possibly Set by `idf-ci gitlab dynamic-pipeline-variables`
    IDF_CI_IS_DEBUG_PIPELINE: t.Optional[bool] = None
    IDF_CI_SELECT_BY_FILTER_EXPR: t.Optional[str] = None
    IDF_CI_SELECT_ALL_PYTEST_CASES: t.Optional[bool] = None

    @property
    def select_all_pytest_cases(self) -> bool:
        """Determine if all pytest cases should be selected.

        :returns: True if this is a full pipeline run, False otherwise
        """
        if self.IDF_CI_SELECT_ALL_PYTEST_CASES == '1':
            logger.info('Selecting all pytest cases since `IDF_CI_SELECT_ALL_PYTEST_CASES=1`')
            return True

        return False

    @property
    def select_by_filter_expr(self) -> t.Optional[str]:
        """Get the filter expression for pytest cases.

        :returns: The filter expression if set, None otherwise
        """
        if self.IDF_CI_SELECT_BY_FILTER_EXPR:
            logger.info('Selecting pytest cases with filter expression: %s', self.IDF_CI_SELECT_BY_FILTER_EXPR)
            return self.IDF_CI_SELECT_BY_FILTER_EXPR

        return None
