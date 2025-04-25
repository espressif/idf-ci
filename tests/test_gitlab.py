# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

import pytest

from idf_ci.idf_gitlab.scripts import pipeline_variables


@pytest.mark.parametrize(
    'env_vars,expected',
    [
        # Non-MR pipeline case
        (
            {'CI_COMMIT_SHA': '12345abcde'},
            {
                'IDF_CI_SELECT_ALL_PYTEST_CASES': '1',
                'PIPELINE_COMMIT_SHA': '12345abcde',
            },
        ),
        # MR pipeline with python constraint branch
        (
            {
                'CI_MERGE_REQUEST_IID': '123',
                'CI_COMMIT_SHA': 'bcdefa54321',
                'CI_MERGE_REQUEST_SOURCE_BRANCH_SHA': 'abcdef12345',
                'CI_PYTHON_CONSTRAINT_BRANCH': 'some-branch',
            },
            {
                'IDF_CI_SELECT_ALL_PYTEST_CASES': '1',
                'PIPELINE_COMMIT_SHA': 'abcdef12345',
            },
        ),
        # MR pipeline with BUILD_AND_TEST_ALL_APPS label
        (
            {
                'CI_MERGE_REQUEST_IID': '123',
                'CI_COMMIT_SHA': 'bcdefa54321',
                'CI_MERGE_REQUEST_SOURCE_BRANCH_SHA': 'abcdef12345',
                'CI_MERGE_REQUEST_LABELS': 'BUILD_AND_TEST_ALL_APPS,some-other-label',
            },
            {
                'IDF_CI_SELECT_ALL_PYTEST_CASES': '1',
                'PIPELINE_COMMIT_SHA': 'abcdef12345',
            },
        ),
        # MR pipeline with Test Case Filters in description
        (
            {
                'CI_MERGE_REQUEST_IID': '123',
                'CI_COMMIT_SHA': 'bcdefa54321',
                'CI_MERGE_REQUEST_SOURCE_BRANCH_SHA': 'abcdef12345',
                'CI_MERGE_REQUEST_DESCRIPTION': """
## Dynamic Pipeline Configuration

```yaml
Test Case Filters:
  - filter1
  - filter2
```

Some other text
""",
            },
            {
                'IDF_CI_SELECT_BY_FILTER_EXPR': 'filter1 or filter2',
                'IDF_CI_IS_DEBUG_PIPELINE': '1',
                'PIPELINE_COMMIT_SHA': 'abcdef12345',
            },
        ),
        # MR pipeline with no special conditions
        (
            {
                'CI_MERGE_REQUEST_IID': '123',
                'CI_COMMIT_SHA': 'bcdefa54321',
                'CI_MERGE_REQUEST_SOURCE_BRANCH_SHA': 'abcdef12345',
            },
            {
                'PIPELINE_COMMIT_SHA': 'abcdef12345',
            },
        ),
    ],
)
def test_pipeline_variables(monkeypatch, env_vars, expected):
    for env_var in [var for var in os.environ if var.startswith(('CI_', 'IDF_CI_'))]:
        monkeypatch.delenv(env_var, raising=False)

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    result = pipeline_variables()
    assert result == expected


def test_pipeline_variables_no_env_vars(monkeypatch):
    for env_var in [var for var in os.environ if var.startswith(('CI_', 'IDF_CI_'))]:
        monkeypatch.delenv(env_var, raising=False)

    result = pipeline_variables()
    assert result == {'IDF_CI_SELECT_ALL_PYTEST_CASES': '1'}
