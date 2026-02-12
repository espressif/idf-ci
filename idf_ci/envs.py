# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import typing as t

from pydantic_settings import (
    BaseSettings,
)

logger = logging.getLogger(__name__)


class GitlabEnvVars(BaseSettings):
    # Pipeline Control Variables
    CHANGED_FILES_SEMICOLON_SEPARATED: str | None = None
    """Semicolon-separated list of changed files in the pipeline."""

    # GitLab API Authentication
    GITLAB_HTTPS_SERVER: str = 'https://gitlab.com'
    """GitLab server URL for API calls."""

    GITLAB_ACCESS_TOKEN: str | None = None
    """Access token for GitLab API authentication."""

    # S3 Storage Configuration
    IDF_S3_SERVER: str | None = None
    """S3 server endpoint URL."""

    IDF_S3_ACCESS_KEY: str | None = None
    """S3 access key for authentication."""

    IDF_S3_SECRET_KEY: str | None = None
    """S3 secret key for authentication."""

    IDF_S3_TIMEOUT_TOTAL: float = 300.0
    """S3 total request timeout in seconds."""

    # other env vars used
    IDF_PATH: str = ''
    """Path to the ESP-IDF directory."""

    # Possibly Set by `idf-ci gitlab dynamic-pipeline-variables`
    IDF_CI_IS_DEBUG_PIPELINE: bool | None = None
    """Flag indicating whether this is a debug pipeline."""

    IDF_CI_SELECT_BY_FILTER_EXPR: str | None = None
    """Filter expression for selecting pytest cases."""

    IDF_CI_SELECT_ALL_PYTEST_CASES: bool | None = None
    """Flag indicating whether to select all pytest cases."""

    IDF_CI_SELECT_BY_TARGETS: str | None = None
    """comma-separated list of targets to be built and tested."""

    IDF_CI_BUILD_ONLY_TEST_RELATED_APPS: bool | None = None
    """Flag indicating whether to build only test-related apps."""

    IDF_CI_BUILD_ONLY_NON_TEST_RELATED_APPS: bool | None = None
    """Flag indicating whether to build only non-test-related apps."""

    def model_post_init(self, __context: t.Any) -> None:
        if self.IDF_CI_BUILD_ONLY_TEST_RELATED_APPS and self.IDF_CI_BUILD_ONLY_NON_TEST_RELATED_APPS:
            raise SystemExit(
                'Cannot set both `IDF_CI_BUILD_ONLY_TEST_RELATED_APPS` and `IDF_CI_BUILD_ONLY_NON_TEST_RELATED_APPS`'
            )

    @property
    def select_all_pytest_cases(self) -> bool:
        """Determine if all pytest cases should be selected.

        :returns: True if this is a full pipeline run, False otherwise
        """
        if self.IDF_CI_SELECT_ALL_PYTEST_CASES:
            logger.info('Selecting all pytest cases since `IDF_CI_SELECT_ALL_PYTEST_CASES=1`')
            return True

        return False

    @property
    def select_by_filter_expr(self) -> str | None:
        """Get the filter expression for pytest cases.

        :returns: The filter expression if set, None otherwise
        """
        if self.IDF_CI_SELECT_BY_FILTER_EXPR:
            logger.info('Selecting pytest cases with filter expression: %s', self.IDF_CI_SELECT_BY_FILTER_EXPR)
            return self.IDF_CI_SELECT_BY_FILTER_EXPR

        return None

    @property
    def select_by_targets(self) -> list[str] | None:
        """Get the list of targets to be built and tested.

        :returns: List of targets if set, None otherwise
        """
        if self.IDF_CI_SELECT_BY_TARGETS:
            targets = [_t.strip() for _t in self.IDF_CI_SELECT_BY_TARGETS.split(',') if _t.strip()]
            logger.info('Selecting targets: %s. ONLY build and test these targets!!!', targets)
            return targets

        return None
