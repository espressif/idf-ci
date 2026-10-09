# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

import pytest
import yaml
from idf_build_apps import App, CMakeApp
from jinja2 import Environment

from idf_ci.cli import click_cli
from idf_ci.idf_gitlab import ArtifactManager
from idf_ci.idf_gitlab.api import ArtifactError
from idf_ci.idf_gitlab.pipeline import _parallel_count, build_child_pipeline
from idf_ci.idf_gitlab.pipeline import test_child_pipeline as generate_test_child_pipeline
from idf_ci.idf_gitlab.scripts import pipeline_variables
from idf_ci.idf_pytest.models import GroupedPytestCases
from idf_ci.scripts import preprocess_args
from idf_ci.settings import CiSettings, _refresh_ci_settings, scoped_ci_settings


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
            'IDF_CI_SELECT_BY_FILTER_EXPR': 'filter1 or filter2',
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
                    'job_image': 'custom-build:1',
                },
                'test_pipeline': {
                    'job_name_suffix': ':test-sfx',
                    'job_image': 'custom-test:2',
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
        toolchain='gcc',
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
    generate_script = '\n'.join(generate_test_pipeline_job['script'])
    assert """--config 'gitlab.build_pipeline.job_name_suffix=":build-sfx"'""" in generate_script
    assert """--config 'gitlab.build_pipeline.job_image="custom-build:1"'""" in generate_script
    assert """--config 'gitlab.test_pipeline.job_name_suffix=":test-sfx"'""" in generate_script
    assert """--config 'gitlab.test_pipeline.job_image="custom-test:2"'""" in generate_script

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
        extra_jobs='',
    )
    test_pipeline = yaml.safe_load(test_rendered)

    default_test_template = test_pipeline[settings.gitlab.test_pipeline.job_template_name]
    test_job = test_pipeline['esp32 - generic:test-sfx']

    assert default_test_template['image'] == 'custom-test:2'
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


def test_generate_test_child_pipeline_forwards_empty_suffixes():
    """Empty suffixes are forwarded with the same quoting and leave job names unsuffixed."""
    settings = CiSettings()
    env = Environment()
    build_rendered = env.from_string(settings.gitlab.build_pipeline.yaml_jinja).render(
        settings=settings,
        job_template='',
        jobs='',
        test_related_apps_count=1,
        toolchain='gcc',
    )
    generate_script = '\n'.join(yaml.safe_load(build_rendered)['generate_test_child_pipeline']['script'])

    assert """--config 'gitlab.build_pipeline.job_name_suffix=""'""" in generate_script
    assert """--config 'gitlab.build_pipeline.job_image="espressif/idf:latest"'""" in generate_script
    assert """--config 'gitlab.test_pipeline.job_name_suffix=""'""" in generate_script
    assert """--config 'gitlab.test_pipeline.job_image="python:3-slim"'""" in generate_script


class _FakeItem:
    def __init__(self, nodeid: str):
        self.nodeid = nodeid


class _FakeCase:
    def __init__(self, target_selector, env_selector, runner_tags, nodeid):
        self.target_selector = target_selector
        self.env_selector = env_selector
        self.runner_tags = tuple(runner_tags)
        self.item = _FakeItem(nodeid)


def _grouped_cases(*cases):
    return GroupedPytestCases(list(cases))


def _write_test_pipeline(monkeypatch, settings, tmp_path, cases):
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    yaml_output = tmp_path / 'test_child_pipeline.yml'
    generate_test_child_pipeline(str(yaml_output), cases=cases)
    return yaml.safe_load(yaml_output.read_text())


class TestExtraJobsJinja:
    def test_empty_fragment_keeps_generated_jobs_only(self, monkeypatch, tmp_path):
        settings = CiSettings()
        pipeline = _write_test_pipeline(
            monkeypatch,
            settings,
            tmp_path,
            _grouped_cases(_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_example.py::test_case')),
        )

        assert 'esp32 - generic' in pipeline
        assert list(pipeline) == [
            'workflow',
            settings.gitlab.test_pipeline.job_template_name,
            'esp32 - generic',
        ]

    def test_rendered_conditional_fragment_appends_job(self, monkeypatch, tmp_path):
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_name_suffix': ':idf-latest',
                        'extra_jobs_jinja': """
{% if settings.gitlab.test_pipeline.job_name_suffix == ":idf-latest" %}
coverage{{ settings.gitlab.test_pipeline.job_name_suffix }}:
  needs:
    - job: "esp32 - generic{{ settings.gitlab.test_pipeline.job_name_suffix }}"
  image: "{{ settings.gitlab.test_pipeline.job_image }}"
  script:
    - generate-coverage
{% endif %}
""",
                    },
                },
            }
        )
        pipeline = _write_test_pipeline(
            monkeypatch,
            settings,
            tmp_path,
            _grouped_cases(_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_example.py::test_case')),
        )

        assert list(pipeline)[-1] == 'coverage:idf-latest'
        assert pipeline['coverage:idf-latest']['needs'] == [{'job': 'esp32 - generic:idf-latest'}]
        assert pipeline['coverage:idf-latest']['image'] == settings.gitlab.test_pipeline.job_image
        assert pipeline['coverage:idf-latest']['script'] == ['generate-coverage']

    def test_fake_pass_skips_extra_jobs(self, monkeypatch, tmp_path):
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'extra_jobs_jinja': """
coverage:
  script:
    - generate-coverage
""",
                    },
                },
            }
        )
        pipeline = _write_test_pipeline(monkeypatch, settings, tmp_path, GroupedPytestCases([]))

        assert pipeline['fake_pass']['script'] == ['echo "skip the entire child pipeline"']
        assert 'coverage' not in pipeline


class TestJobVariablesJinja:
    def test_empty_output_keeps_only_nodes(self, monkeypatch, tmp_path):
        settings = CiSettings()
        pipeline = _write_test_pipeline(
            monkeypatch,
            settings,
            tmp_path,
            _grouped_cases(_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_example.py::test_case')),
        )

        assert list(pipeline['esp32 - generic']['variables']) == ['nodes']

    def test_one_variable_applied_to_every_job(self, monkeypatch, tmp_path):
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_variables_jinja': 'SHARED: "yes: #keep"',
                    },
                },
            }
        )
        pipeline = _write_test_pipeline(
            monkeypatch,
            settings,
            tmp_path,
            _grouped_cases(
                _FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_a.py::test_a'),
                _FakeCase('esp32s2', 'generic', ['esp32s2', 'generic'], 'tests/test_b.py::test_b'),
            ),
        )

        for job_name in ('esp32 - generic', 'esp32s2 - generic'):
            variables = pipeline[job_name]['variables']
            assert list(variables) == ['nodes', 'SHARED']
            assert variables['SHARED'] == 'yes: #keep'

    def test_latest_only_output(self, monkeypatch, tmp_path):
        latest = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_name_suffix': ':idf-latest',
                        'job_variables_jinja': """
{% if settings.gitlab.test_pipeline.job_name_suffix == ":idf-latest" %}
MQTT_CONFORMANCE_SETUP_OPENOCD: "1"
{% endif %}
""",
                    },
                },
            }
        )
        other = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_name_suffix': ':idf-release',
                        'job_variables_jinja': latest.gitlab.test_pipeline.job_variables_jinja,
                    },
                },
            }
        )
        cases = _grouped_cases(_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_example.py::test_case'))

        latest_pipeline = _write_test_pipeline(monkeypatch, latest, tmp_path, cases)
        other_dir = tmp_path / 'other'
        other_dir.mkdir()
        other_pipeline = _write_test_pipeline(monkeypatch, other, other_dir, cases)

        assert latest_pipeline['esp32 - generic:idf-latest']['variables']['MQTT_CONFORMANCE_SETUP_OPENOCD'] == '1'
        assert 'MQTT_CONFORMANCE_SETUP_OPENOCD' not in other_pipeline['esp32 - generic:idf-release']['variables']

    def test_condition_based_on_current_job(self, monkeypatch, tmp_path):
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_variables_jinja': """
{% if job['name'] == 'esp32 - generic' %}
ONLY_ESP32: "1"
{% endif %}
""",
                    },
                },
            }
        )
        pipeline = _write_test_pipeline(
            monkeypatch,
            settings,
            tmp_path,
            _grouped_cases(
                _FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_a.py::test_a'),
                _FakeCase('esp32s2', 'generic', ['esp32s2', 'generic'], 'tests/test_b.py::test_b'),
            ),
        )

        assert pipeline['esp32 - generic']['variables']['ONLY_ESP32'] == '1'
        assert 'ONLY_ESP32' not in pipeline['esp32s2 - generic']['variables']

    def test_invalid_non_mapping_output(self, monkeypatch, tmp_path):
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_variables_jinja': '- not-a-mapping',
                    },
                },
            }
        )
        monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)

        with pytest.raises(ValueError, match='must render to a YAML mapping of job variables, got list'):
            generate_test_child_pipeline(
                str(tmp_path / 'test_child_pipeline.yml'),
                cases=_grouped_cases(
                    _FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_example.py::test_case')
                ),
            )

    def test_invalid_yaml_output(self, monkeypatch, tmp_path):
        settings = CiSettings.model_validate(
            {
                'gitlab': {
                    'test_pipeline': {
                        'job_variables_jinja': 'MQTT_CONFORMANCE_SETUP_OPENOCD: [unterminated',
                    },
                },
            }
        )
        monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)

        with pytest.raises(ValueError, match='rendered invalid YAML'):
            generate_test_child_pipeline(
                str(tmp_path / 'test_child_pipeline.yml'),
                cases=_grouped_cases(
                    _FakeCase('esp32', 'generic', ['esp32', 'generic'], 'tests/test_example.py::test_case')
                ),
            )


@pytest.mark.parametrize(
    'item_count,runs_per_job,expected',
    [
        (0, 60, 0),
        (1, 60, 1),
        (59, 60, 1),
        (60, 60, 1),
        (61, 60, 2),
        (120, 60, 2),
        (121, 60, 3),
    ],
)
def test_parallel_count(item_count, runs_per_job, expected):
    assert _parallel_count(item_count, runs_per_job) == expected


@pytest.mark.parametrize('toolchain', ['gcc', 'clang'])
def test_build_child_pipeline_toolchain_discovery_and_artifact_namespace(monkeypatch, tmp_path, toolchain):
    settings = CiSettings.model_validate({'gitlab': {'build_enabled_toolchains': ['gcc', 'clang']}})
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    found = []

    def get_apps(**kwargs):
        found.append(os.getenv('IDF_TOOLCHAIN'))
        return [App(str(tmp_path / 'hello_world'), 'esp32', config_name='default')], []

    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_all_apps', get_apps)
    output = tmp_path / f'build_{toolchain}.yml'
    build_child_pipeline(yaml_output=str(output), toolchain=toolchain)

    pipeline = yaml.safe_load(output.read_text())
    assert found == [toolchain]
    assert os.getenv('IDF_TOOLCHAIN') is None
    assert pipeline['variables']['IDF_TOOLCHAIN'] == toolchain
    assert pipeline['variables'].get('IDF_CI_ARTIFACT_NAMESPACE') == ('clang' if toolchain == 'clang' else None)
    assert pipeline['workflow']['name'] == (
        'Build Child Pipeline (clang)' if toolchain == 'clang' else 'Build Child Pipeline'
    )
    assert 'build_non_test_related_apps' not in pipeline
    assert pipeline['build_test_related_apps']['variables']['IDF_CI_BUILD_ONLY_TEST_RELATED_APPS'] == '1'
    assert pipeline['build_test_related_apps']['needs'] == [
        {'pipeline': '$PARENT_PIPELINE_ID', 'job': 'generate_build_child_pipeline'},
        {'pipeline': '$PARENT_PIPELINE_ID', 'job': 'pipeline_variables'},
    ]
    assert (tmp_path / settings.collected_test_related_apps_filepath).exists()


def test_artifact_prefix_isolated_by_namespace(monkeypatch):
    monkeypatch.delenv('IDF_CI_ARTIFACT_NAMESPACE', raising=False)
    manager = ArtifactManager()
    assert manager._build_s3_prefix('abc') == 'espressif/esp-idf/abc/'
    monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', 'clang')
    assert manager._build_s3_prefix('abc') == 'espressif/esp-idf/abc_clang/'
    monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', '../other')
    with pytest.raises(ArtifactError, match='Invalid artifact namespace'):
        manager._build_s3_prefix('abc')


@pytest.mark.parametrize('legacy_toolchain', [None, 'clang'])
def test_omitted_toolchain_preserves_legacy_build_yaml(monkeypatch, tmp_path, runner, legacy_toolchain):
    monkeypatch.delenv('IDF_CI_ARTIFACT_NAMESPACE', raising=False)
    if legacy_toolchain:
        monkeypatch.setenv('IDF_TOOLCHAIN', legacy_toolchain)
    else:
        monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    found = []

    def get_apps(**kwargs):
        found.append(os.getenv('IDF_TOOLCHAIN'))
        return [App(str(tmp_path / 'hello_world'), 'esp32', config_name='default')], []

    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_all_apps', get_apps)
    output = tmp_path / 'build_child_pipeline.yml'
    result = runner.invoke(click_cli, ['gitlab', 'build-child-pipeline', str(output)])
    assert result.exit_code == 0, result.output
    pipeline = yaml.safe_load(output.read_text())

    assert found == [legacy_toolchain]
    assert 'variables' not in pipeline
    assert pipeline['workflow']['name'] == 'Build Child Pipeline'
    assert pipeline['build_test_related_apps']['needs'] == [
        {'pipeline': '$PARENT_PIPELINE_ID', 'job': 'generate_build_child_pipeline'},
        {'pipeline': '$PARENT_PIPELINE_ID', 'job': 'pipeline_variables'},
    ]
    assert 'generate_test_child_pipeline' in pipeline
    assert 'test-child-pipeline' in pipeline


@pytest.mark.parametrize('legacy_toolchain', [None, 'clang'])
def test_omitted_toolchain_preserves_legacy_test_yaml(monkeypatch, tmp_path, legacy_toolchain):
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', CiSettings)
    monkeypatch.delenv('IDF_CI_ARTIFACT_NAMESPACE', raising=False)
    if legacy_toolchain:
        monkeypatch.setenv('IDF_TOOLCHAIN', legacy_toolchain)
    else:
        monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    output = tmp_path / 'test_child_pipeline.yml'
    generate_test_child_pipeline(
        str(output),
        cases=_grouped_cases(_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'test_hello.py::test_hello')),
    )
    pipeline = yaml.safe_load(output.read_text())

    assert 'variables' not in pipeline
    assert pipeline['workflow']['name'] == 'Test Child Pipeline'
    assert 'esp32 - generic' in pipeline


def test_clang_build_automatically_namespaces_its_test_pipeline(monkeypatch, tmp_path):
    settings = CiSettings.model_validate({'gitlab': {'test_enabled_toolchains': ['gcc', 'clang']}})
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    monkeypatch.setenv('IDF_TOOLCHAIN', 'clang')
    monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', 'clang')
    output = tmp_path / 'test_clang.yml'
    generate_test_child_pipeline(
        str(output),
        cases=_grouped_cases(_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'test_hello.py::test_hello')),
    )
    test_pipeline = yaml.safe_load(output.read_text())
    assert test_pipeline['workflow']['name'] == 'Test Child Pipeline (clang)'
    assert test_pipeline['variables'] == {
        'IDF_TOOLCHAIN': 'clang',
        'IDF_CI_ARTIFACT_NAMESPACE': 'clang',
    }


def test_clang_test_generator_rejects_gcc_override(monkeypatch, tmp_path):
    monkeypatch.setenv('IDF_TOOLCHAIN', 'clang')
    monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', 'clang')
    settings = CiSettings.model_validate({'gitlab': {'test_enabled_toolchains': ['gcc', 'clang']}})
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    with pytest.raises(ValueError, match='cannot generate GCC target tests'):
        generate_test_child_pipeline(str(tmp_path / 'test.yml'), cases=GroupedPytestCases([]), toolchain='gcc')


def test_build_child_pipelines_share_parent_job_and_isolate_app_lists(monkeypatch, tmp_path, runner):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CI', '1')
    monkeypatch.delenv('IDF_CI_APP_LIST_SUFFIX', raising=False)
    settings = CiSettings.model_validate({'gitlab': {'build_enabled_toolchains': ['gcc', 'clang']}})
    found = []

    def get_apps(**kwargs):
        selected = os.getenv('IDF_TOOLCHAIN')
        found.append(selected)
        return [], [CMakeApp(str(tmp_path / 'hello_world'), 'esp32', config_name=selected)]

    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_all_apps', get_apps)
    result = runner.invoke(
        click_cli,
        [
            '--config',
            "gitlab.build_enabled_toolchains=['gcc', 'clang']",
            'gitlab',
            'build-child-pipeline',
            'build_child_pipeline.yml',
        ],
    )
    assert result.exit_code == 0, result.output
    with scoped_ci_settings(settings):
        gcc = yaml.safe_load((tmp_path / 'build_child_pipeline.yml').read_text())
        clang = yaml.safe_load((tmp_path / 'build_child_pipeline_clang.yml').read_text())
        assert found == ['gcc', 'clang']
        assert gcc['workflow']['name'] == 'Build Child Pipeline'
        assert clang['workflow']['name'] == 'Build Child Pipeline (clang)'
        assert gcc['build_non_test_related_apps']['needs'] == clang['build_non_test_related_apps']['needs']
        assert gcc['build_non_test_related_apps']['needs'][0]['job'] == 'generate_build_child_pipeline'
        assert clang['variables']['IDF_CI_APP_LIST_SUFFIX'] == 'clang'
        assert 'IDF_CI_APP_LIST_SUFFIX' not in gcc['variables']
        assert settings.collected_non_test_related_apps_filepath == 'non_test_related_apps.txt'
        assert [a.config_name for a in settings.read_apps_from_files(['non_test_related_apps.txt'])] == ['gcc']
        assert [a.config_name for a in settings.read_apps_from_files(['non_test_related_apps_clang.txt'])] == ['clang']
        assert (tmp_path / 'test_related_apps.txt').exists()
        assert (tmp_path / 'test_related_apps_clang.txt').exists()

        monkeypatch.setenv('IDF_CI_APP_LIST_SUFFIX', 'clang')
        assert [a.config_name for a in preprocess_args().non_test_related_apps] == ['clang']
        monkeypatch.delenv('IDF_CI_APP_LIST_SUFFIX')
        assert [a.config_name for a in preprocess_args().non_test_related_apps] == ['gcc']


@pytest.mark.parametrize(
    'test_toolchains,gcc_tests,clang_tests',
    [(['gcc'], True, False), (['gcc', 'clang'], True, True), ([], False, False)],
)
def test_two_build_pipelines_select_test_toolchains(
    monkeypatch, tmp_path, runner, test_toolchains, gcc_tests, clang_tests
):
    monkeypatch.chdir(tmp_path)
    settings = CiSettings.model_validate(
        {
            'gitlab': {
                'build_enabled_toolchains': ['gcc', 'clang'],
                'test_enabled_toolchains': test_toolchains,
            }
        }
    )
    monkeypatch.setattr(
        'idf_ci.idf_gitlab.pipeline.get_all_apps',
        lambda **kwargs: ([CMakeApp(str(tmp_path / 'hello_world'), 'esp32')], []),
    )
    result = runner.invoke(
        click_cli,
        [
            '--config',
            "gitlab.build_enabled_toolchains=['gcc', 'clang']",
            '--config',
            f'gitlab.test_enabled_toolchains={test_toolchains!r}',
            'gitlab',
            'build-child-pipeline',
        ],
    )
    assert result.exit_code == 0, result.output
    with scoped_ci_settings(settings):
        for name, tests_enabled in (
            ('build_child_pipeline.yml', gcc_tests),
            ('build_child_pipeline_clang.yml', clang_tests),
        ):
            pipeline = yaml.safe_load((tmp_path / name).read_text())
            assert 'build_test_related_apps' in pipeline
            assert ('generate_test_child_pipeline' in pipeline) is tests_enabled
            assert ('test-child-pipeline' in pipeline) is tests_enabled
            assert pipeline['build_test_related_apps']['needs'] == [
                {'pipeline': '$PARENT_PIPELINE_ID', 'job': 'generate_build_child_pipeline'},
                {'pipeline': '$PARENT_PIPELINE_ID', 'job': 'pipeline_variables'},
            ]
        assert (tmp_path / 'test_related_apps.txt').exists()
        assert (tmp_path / 'test_related_apps_clang.txt').exists()


def test_filtered_generator_publishes_lists_for_multi_toolchain(monkeypatch, tmp_path, runner):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('IDF_CI_SELECT_BY_FILTER_EXPR', 'test_hello')
    monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    monkeypatch.setattr(
        'idf_ci.idf_gitlab.pipeline.get_all_apps',
        lambda **kwargs: ([CMakeApp(str(tmp_path / 'hello_world'), 'esp32')], []),
    )
    result = runner.invoke(
        click_cli,
        ['--config', "gitlab.build_enabled_toolchains=['gcc', 'clang']", 'gitlab', 'build-child-pipeline'],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'test_related_apps.txt').exists()
    assert (tmp_path / 'test_related_apps_clang.txt').exists()
    assert (tmp_path / 'non_test_related_apps_clang.txt').read_text() == ''
    assert (tmp_path / 'non_test_related_apps.txt').read_text() == ''


def test_build_toolchain_from_settings(monkeypatch, tmp_path):
    settings = CiSettings.model_validate(
        {'gitlab': {'build_enabled_toolchains': ['gcc', 'clang'], 'build_pipeline': {'toolchain': 'clang'}}}
    )
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    found = []

    def get_apps(**kwargs):
        found.append(os.getenv('IDF_TOOLCHAIN'))
        return [App(str(tmp_path / 'hello_world'), 'esp32', config_name='default')], []

    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_all_apps', get_apps)
    output = tmp_path / 'build_clang.yml'
    build_child_pipeline(yaml_output=str(output))
    assert found == ['clang']
    assert os.getenv('IDF_TOOLCHAIN') is None
    assert yaml.safe_load(output.read_text())['variables'] == {
        'IDF_TOOLCHAIN': 'clang',
        'IDF_CI_ARTIFACT_NAMESPACE': 'clang',
    }

    build_child_pipeline(yaml_output=str(output), toolchain='gcc')
    assert found == ['clang', 'gcc']
    assert yaml.safe_load(output.read_text())['variables'] == {'IDF_TOOLCHAIN': 'gcc'}


def test_test_toolchain_from_settings(monkeypatch, tmp_path):
    settings = CiSettings.model_validate(
        {'gitlab': {'test_enabled_toolchains': ['gcc', 'clang'], 'test_pipeline': {'toolchain': 'clang'}}}
    )
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    found = []
    monkeypatch.setattr(
        'idf_ci.idf_gitlab.pipeline.get_pytest_cases',
        lambda: (
            found.append(os.getenv('IDF_TOOLCHAIN'))
            or [_FakeCase('esp32', 'generic', ['esp32', 'generic'], 'test_hello.py::test_hello')]
        ),
    )
    output = tmp_path / 'test_clang.yml'
    generate_test_child_pipeline(str(output))
    assert found == ['clang']
    assert os.getenv('IDF_TOOLCHAIN') is None
    assert yaml.safe_load(output.read_text())['variables'] == {
        'IDF_TOOLCHAIN': 'clang',
        'IDF_CI_ARTIFACT_NAMESPACE': 'clang',
    }
