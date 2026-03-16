# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

import pytest
from jinja2 import Environment

from idf_ci.idf_gitlab.scripts import pipeline_variables
from idf_ci.settings import CiSettings


class TestPipelineVariables:
    @pytest.fixture(autouse=True)
    def setup_clean_env(self, monkeypatch):
        for env_var in [var for var in os.environ if var.startswith(('CI_', 'IDF_CI_'))]:
            monkeypatch.delenv(env_var, raising=False)

    def test_non_mr_pipeline(self, monkeypatch):
        monkeypatch.setenv('CI_COMMIT_SHA', '12345abcde')

        assert pipeline_variables() == {
            'IDF_CI_SELECT_ALL_PYTEST_CASES': '1',
            'PIPELINE_COMMIT_SHA': '12345abcde',
        }

    def test_mr_python_constraint(self, monkeypatch):
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '123')
        monkeypatch.setenv('CI_COMMIT_SHA', 'bcdefa54321')
        monkeypatch.setenv('CI_MERGE_REQUEST_SOURCE_BRANCH_SHA', 'abcdef12345')
        monkeypatch.setenv('CI_PYTHON_CONSTRAINT_BRANCH', 'some-branch')

        assert pipeline_variables() == {
            'IDF_CI_SELECT_ALL_PYTEST_CASES': '1',
            'PIPELINE_COMMIT_SHA': 'abcdef12345',
        }

    def test_mr_build_all_apps(self, monkeypatch):
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '123')
        monkeypatch.setenv('CI_COMMIT_SHA', 'bcdefa54321')
        monkeypatch.setenv('CI_MERGE_REQUEST_SOURCE_BRANCH_SHA', 'abcdef12345')
        monkeypatch.setenv('CI_MERGE_REQUEST_LABELS', 'BUILD_AND_TEST_ALL_APPS,some-other-label')

        assert pipeline_variables() == {
            'IDF_CI_SELECT_ALL_PYTEST_CASES': '1',
            'PIPELINE_COMMIT_SHA': 'abcdef12345',
        }

    def test_mr_test_filters(self, monkeypatch):
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '123')
        monkeypatch.setenv('CI_COMMIT_SHA', 'bcdefa54321')
        monkeypatch.setenv('CI_MERGE_REQUEST_SOURCE_BRANCH_SHA', 'abcdef12345')
        monkeypatch.setenv(
            'CI_MERGE_REQUEST_DESCRIPTION',
            '## Dynamic Pipeline Configuration\n\n'
            '```yaml\n'
            'Test Case Filters:\n'
            '  - filter1\n'
            '  - filter2\n'
            '```\n\n'
            'Some other text',
        )

        assert pipeline_variables() == {
            'IDF_CI_SELECT_BY_FILTER_EXPR': '"filter1 or filter2"',
            'IDF_CI_IS_DEBUG_PIPELINE': '1',
            'PIPELINE_COMMIT_SHA': 'abcdef12345',
        }

    def test_mr_no_special_conditions(self, monkeypatch):
        monkeypatch.setenv('CI_MERGE_REQUEST_IID', '123')
        monkeypatch.setenv('CI_COMMIT_SHA', 'bcdefa54321')
        monkeypatch.setenv('CI_MERGE_REQUEST_SOURCE_BRANCH_SHA', 'abcdef12345')

        assert pipeline_variables() == {'PIPELINE_COMMIT_SHA': 'abcdef12345'}

    def test_no_env_vars(self):
        assert pipeline_variables() == {'IDF_CI_SELECT_ALL_PYTEST_CASES': '1'}


class TestTestPipelineJobTemplate:
    """Test job template rendering for the test child pipeline."""

    def test_job_before_script_extra_rendered_in_template(self):
        """Extra before_script commands are appended in the rendered test job template."""
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_before_script_extra': [
                            'apt-get update',
                            'pip install some-test-dep',
                        ],
                    },
                },
            }
        )
        env = Environment()
        template = env.from_string(settings.gitlab.test_pipeline.job_template_jinja)
        rendered = template.render(settings=settings)

        assert 'before_script:' in rendered
        assert '- pip install -U idf-ci' in rendered
        assert '- apt-get update' in rendered
        assert '- pip install some-test-dep' in rendered

    def test_job_before_script_extra_empty_keeps_only_default(self):
        """With no extra commands, before_script contains only the default pip install."""
        settings = CiSettings()
        env = Environment()
        template = env.from_string(settings.gitlab.test_pipeline.job_template_jinja)
        rendered = template.render(settings=settings)

        assert 'before_script:' in rendered
        assert '- pip install -U idf-ci' in rendered
        # No extra before_script commands when job_before_script_extra is empty
        assert '- apt-get update' not in rendered
        assert '- pip install some-test-dep' not in rendered
