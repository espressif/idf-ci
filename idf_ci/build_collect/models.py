# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import typing as t
from enum import Enum

from idf_build_apps.constants import BuildStatus
from pydantic import BaseModel, SerializerFunctionWrapHandler, field_serializer, model_serializer


class AppStatus(str, Enum):
    """App status for HTML format."""

    UNKNOWN = ('U', 'Unknown')
    SHOULD_BE_BUILT = ('B', 'Should be built')
    SHOULD_BE_BUILT_AND_TESTS_ENABLED = ('BT', 'Should be built and all test cases are enabled')
    SHOULD_BE_BUILT_AND_TESTS_SKIPPED = ('BS', 'Should be built and all test cases are skipped')
    SHOULD_BE_BUILT_AND_TESTS_MIXED = ('BTS', 'Should be built, some test cases are enabled and some are skipped')
    DISABLED = ('D', 'Disabled')
    DISABLED_AND_TESTS_ENABLED = ('DT', 'Disabled and all test cases are enabled')
    DISABLED_AND_TESTS_SKIPPED = ('DS', 'Disabled and all test cases are skipped')
    DISABLED_AND_TESTS_MIXED = ('DTS', 'Disabled, some test cases are enabled and some are skipped')

    def __new__(cls, value: str, *args, **kwargs):
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    def __init__(self, _: str, description: str):
        self._description_ = description

    @property
    def description(self) -> str:
        return self._description_


class AppKey(t.NamedTuple):
    """Unique identifier for an app."""

    path: str
    target: str
    config: str


class CaseInfo(BaseModel):
    """Information about a test case attached to an app."""

    name: str
    caseid: str
    disabled: bool = False
    disabled_by_manifest: bool = False
    disabled_by_marker: bool = False
    skip_reason: str = ''
    test_comment: str = ''

    @model_serializer(mode='wrap')
    def serialize(self, handler: SerializerFunctionWrapHandler) -> dict[str, t.Any]:
        serialized = handler(self)

        if not self.disabled:
            return {'name': self.name, 'caseid': self.caseid}

        return serialized


class AppInfo(BaseModel):
    """Information about a buildable app."""

    target: str
    config: str
    build_status: BuildStatus
    build_comment: str = ''
    test_comment: str = ''
    test_cases: list[CaseInfo] = []
    has_temp_rule: bool = False
    matched_rules: dict[str, list[str]] = {}

    @field_serializer('build_status')
    def serialize_build_status(self, status: BuildStatus) -> str:
        return status.value


class MissingAppInfo(BaseModel):
    """Information about a missing app referenced by test cases."""

    target: str
    config: str
    test_cases: list[CaseInfo] = []


class ProjectInfo(BaseModel):
    """Collection of apps and missing apps for a one path (project)."""

    apps: list[AppInfo] = []
    missing_apps: list[MissingAppInfo] = []


class Summary(BaseModel):
    """Statistics of the collected apps and test cases."""

    total_projects: int = 0
    total_apps: int = 0
    total_test_cases: int = 0
    total_test_cases_used: int = 0
    total_test_cases_disabled: int = 0
    total_test_cases_missing_app: int = 0


class CollectResult(BaseModel):
    summary: Summary = Summary()
    projects: dict[str, ProjectInfo] = {}
