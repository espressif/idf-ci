# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

import pytest
import yaml
from jinja2 import Environment

from idf_ci.idf_gitlab import ArtifactManager
from idf_ci.idf_gitlab.scripts import pipeline_variables
from idf_ci.settings import CiSettings, _refresh_ci_settings


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


def test_get_s3_path_preserves_nested_relative_path_from_config_root(tmp_path, monkeypatch):
    repo_root = tmp_path
    nested_cwd = repo_root / 'examples' / 'get-started'
    build_dir = nested_cwd / 'hello_world' / 'build_esp32_default'
    build_dir.mkdir(parents=True)
    (repo_root / '.idf_ci.toml').write_text(
        """
[gitlab]
project = "espressif/esp-idf"

[gitlab.artifacts.s3]
enable = true
"""
    )

    monkeypatch.chdir(nested_cwd)
    monkeypatch.delenv('IDF_PATH', raising=False)
    _refresh_ci_settings()

    s3_path = ArtifactManager()._get_s3_path('espressif/esp-idf/1/', build_dir / 'flash.zip')

    assert s3_path == 'espressif/esp-idf/1/examples/get-started/hello_world/build_esp32_default/flash.zip'


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


def test_rendered_gitlab_pipelines_include_job_name_suffixes_and_artifacts():
    """Rendered build and test pipeline YAMLs keep suffix references and artifact wiring consistent."""
    settings = CiSettings.model_validate(
        {
            'gitlab': {
                'build_pipeline': {
                    'job_name_suffix': ':build-sfx',
                },
                'test_pipeline': {
                    'job_name_suffix': ':test-sfx',
                },
            },
        }
    )
    env = Environment()

    build_jobs = env.from_string(settings.gitlab.build_pipeline.jobs_jinja).render(
        settings=settings,
        test_related_apps_count=1,
        test_related_parallel_count=1,
        non_test_related_apps_count=1,
        non_test_related_parallel_count=1,
    )
    build_rendered = env.from_string(settings.gitlab.build_pipeline.yaml_jinja).render(
        settings=settings,
        job_template='',
        jobs=build_jobs,
        test_related_apps_count=1,
    )
    build_pipeline = yaml.safe_load(build_rendered)

    build_test_job = build_pipeline['build_test_related_apps:build-sfx']
    build_non_test_job = build_pipeline['build_non_test_related_apps:build-sfx']
    generate_test_pipeline_job = build_pipeline['generate_test_child_pipeline:build-sfx']
    trigger_test_pipeline_job = build_pipeline['test-child-pipeline:build-sfx']

    assert build_test_job['extends'] == settings.gitlab.build_pipeline.job_template_name
    assert build_test_job['needs'] == [
        {
            'pipeline': '$PARENT_PIPELINE_ID',
            'job': 'generate_build_child_pipeline',
        },
        {
            'pipeline': '$PARENT_PIPELINE_ID',
            'job': 'pipeline_variables',
        },
    ]
    assert build_non_test_job['extends'] == settings.gitlab.build_pipeline.job_template_name
    assert generate_test_pipeline_job['needs'] == ['build_test_related_apps:build-sfx']
    assert generate_test_pipeline_job['artifacts']['paths'] == [
        *settings.gitlab.artifacts.native.build_job_filepatterns,
        settings.gitlab.test_pipeline.yaml_filename,
    ]
    assert trigger_test_pipeline_job['needs'] == ['generate_test_child_pipeline:build-sfx']
    assert trigger_test_pipeline_job['trigger']['include'] == [
        {
            'artifact': settings.gitlab.test_pipeline.yaml_filename,
            'job': 'generate_test_child_pipeline:build-sfx',
        }
    ]

    test_jobs = env.from_string(settings.gitlab.test_pipeline.jobs_jinja).render(
        settings=settings,
        jobs=[
            {
                'name': 'esp32 - generic',
                'tags': ['esp32', 'generic'],
                'parallel_count': 1,
                'nodes': '"\'tests/test_example.py::test_case\'"',
            }
        ],
    )
    test_rendered = env.from_string(settings.gitlab.test_pipeline.yaml_jinja).render(
        settings=settings,
        default_template=env.from_string(settings.gitlab.test_pipeline.job_template_jinja).render(settings=settings),
        jobs=test_jobs,
    )
    test_pipeline = yaml.safe_load(test_rendered)

    default_test_template = test_pipeline[settings.gitlab.test_pipeline.job_template_name]
    test_job = test_pipeline['esp32 - generic:test-sfx']

    assert default_test_template['needs'] == [
        {
            'pipeline': '$PARENT_PIPELINE_ID',
            'job': 'generate_test_child_pipeline:build-sfx',
        }
    ]
    assert default_test_template['artifacts']['paths'] == settings.gitlab.artifacts.native.test_job_filepatterns
    assert test_job['extends'] == [settings.gitlab.test_pipeline.job_template_name]
    assert test_job['tags'] == ['esp32', 'generic']
    assert test_job['variables']['nodes'] == "'tests/test_example.py::test_case'"
