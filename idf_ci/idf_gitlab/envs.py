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
    # Pipeline Control Variables
    CHANGED_FILES_SEMICOLON_SEPARATED: UndefinedOr[str] = UNDEF

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
    IDF_CI_IS_DEBUG_PIPELINE: UndefinedOr[bool] = UNDEF
    IDF_CI_SELECT_BY_FILTER_EXPR: UndefinedOr[str] = UNDEF
    IDF_CI_SELECT_ALL_PYTEST_CASES: UndefinedOr[bool] = UNDEF

    @property
    def select_all_pytest_cases(self) -> bool:
        """Determine if all pytest cases should be selected.

        :returns: True if this is a full pipeline run, False otherwise
        """
        if is_defined_and_satisfies(self.IDF_CI_SELECT_ALL_PYTEST_CASES, lambda x: x == '1'):
            logger.info('Selecting all pytest cases since `IDF_CI_SELECT_ALL_PYTEST_CASES=1`')
            return True

        return False
