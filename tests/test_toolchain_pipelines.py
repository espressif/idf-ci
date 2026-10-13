# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path

import pytest
import yaml
from conftest import create_project
from idf_build_apps import CMakeApp
from idf_build_apps.manifest import DEFAULT_BUILD_TARGETS
from pydantic import ValidationError

from idf_ci.cli import click_cli
from idf_ci.idf_gitlab.pipeline import build_child_pipeline
from idf_ci.idf_gitlab.pipeline import test_child_pipeline as generate_test_child_pipeline
from idf_ci.scripts import preprocess_args
from idf_ci.settings import CiSettings, _refresh_ci_settings, toolchain_filename


@pytest.fixture(autouse=True)
def clear_cli_overrides(monkeypatch):
    monkeypatch.setattr(CiSettings, 'CLI_OVERRIDES', {})


def test_one_command_generates_isolated_build_yamls_and_app_lists(monkeypatch, tmp_path, runner):
    observed = []

    def collect(**kwargs):
        observed.append((os.environ.get('IDF_TOOLCHAIN'), kwargs))
        return [CMakeApp(app_dir='examples/hello', target='esp32')], []

    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_all_apps', collect)
    monkeypatch.setenv('IDF_TOOLCHAIN', 'original')
    result = runner.invoke(
        click_cli,
        [
            '--config',
            "gitlab.build_enabled_toolchains=['gcc','clang']",
            '--config',
            "gitlab.test_enabled_toolchains=['gcc']",
            'gitlab',
            'build-child-pipeline',
            str(tmp_path / 'build.yml'),
        ],
    )
    assert result.exit_code == 0, result.output
    assert [toolchain for toolchain, _ in observed] == ['gcc', 'clang']
    assert os.environ['IDF_TOOLCHAIN'] == 'original'

    gcc = yaml.safe_load((tmp_path / 'build.yml').read_text())
    clang = yaml.safe_load((tmp_path / 'build_clang.yml').read_text())
    assert gcc['variables'] == {'IDF_TOOLCHAIN': 'gcc'}
    assert clang['variables'] == {
        'IDF_TOOLCHAIN': 'clang',
        'IDF_CI_ARTIFACT_NAMESPACE': 'clang',
    }
    assert 'generate_test_child_pipeline' in gcc
    assert 'test-child-pipeline' in gcc
    assert 'generate_test_child_pipeline' not in clang
    assert 'test-child-pipeline' not in clang
    assert gcc['test-child-pipeline']['trigger']['include'][0]['artifact'] == 'test_child_pipeline.yml'
    assert (tmp_path / 'build_clang.yml').is_file()
    assert (tmp_path / 'build.yml').is_file()
    # App lists are written in the command's working directory, not next to the YAML output.
    assert os.path.exists('test_related_apps.txt')
    assert os.path.exists('test_related_apps_clang.txt')
    assert os.path.exists('non_test_related_apps.txt')
    assert os.path.exists('non_test_related_apps_clang.txt')


def test_build_discovery_restores_unset_toolchain_on_failure(monkeypatch):
    monkeypatch.delenv('IDF_TOOLCHAIN', raising=False)
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_all_apps', lambda **kwargs: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        build_child_pipeline()
    assert 'IDF_TOOLCHAIN' not in os.environ


def test_test_enabled_clang_uses_matching_artifact_and_namespace(monkeypatch, tmp_path):
    settings = CiSettings.model_validate(
        {
            'gitlab': {
                'build_enabled_toolchains': ['gcc', 'clang'],
                'test_enabled_toolchains': ['clang'],
                'test_pipeline': {'yaml_filename': 'target.yml'},
            }
        }
    )
    monkeypatch.setattr('idf_ci.idf_gitlab.pipeline.get_ci_settings', lambda: settings)
    monkeypatch.setattr(
        'idf_ci.idf_gitlab.pipeline.get_all_apps',
        lambda **kwargs: ([CMakeApp(app_dir='examples/hello', target='esp32')], []),
    )
    build_child_pipeline(yaml_output=str(tmp_path / 'build.yml'))
    gcc = yaml.safe_load((tmp_path / 'build.yml').read_text())
    clang = yaml.safe_load((tmp_path / 'build_clang.yml').read_text())
    assert 'test-child-pipeline' not in gcc
    assert clang['test-child-pipeline']['trigger']['include'][0]['artifact'] == 'target_clang.yml'
    assert 'gitlab test-child-pipeline --toolchain "clang"' in '\n'.join(
        clang['generate_test_child_pipeline']['script']
    )
    assert '"target_clang.yml"' in '\n'.join(clang['generate_test_child_pipeline']['script'])
    assert clang['generate_test_child_pipeline']['artifacts']['paths'][-1] == 'target_clang.yml'

    from idf_ci.idf_pytest.models import GroupedPytestCases

    generate_test_child_pipeline(
        cases=GroupedPytestCases([]), toolchain='clang', yaml_output=str(tmp_path / 'test.yml')
    )
    assert 'fake_pass' in yaml.safe_load((tmp_path / 'test.yml').read_text())


def test_build_reads_only_selected_toolchain_lists(monkeypatch, tmp_path):
    monkeypatch.setenv('CI', 'true')
    monkeypatch.setenv('IDF_TOOLCHAIN', 'clang')
    (tmp_path / 'test_related_apps.txt').write_text('invalid gcc data\n')
    (tmp_path / 'test_related_apps_clang.txt').write_text(
        CMakeApp(app_dir='examples/hello', target='esp32').model_dump_json() + '\n'
    )
    (tmp_path / 'non_test_related_apps_clang.txt').write_text('')
    _refresh_ci_settings()
    args = preprocess_args()
    assert args.test_related_apps is not None
    assert len(args.test_related_apps) == 1
    assert args.test_related_apps[0].target == 'esp32'
    assert args.non_test_related_apps == []


def test_namespace_keeps_gcc_variant_app_lists_separate(monkeypatch, tmp_path, runner):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.idf_ci.toml').write_text('')
    monkeypatch.setattr(
        'idf_ci.idf_gitlab.pipeline.get_all_apps',
        lambda **kwargs: (
            [CMakeApp(app_dir='examples/buildv2' if os.getenv('IDF_BUILD_V2') else 'examples/gcc', target='esp32')],
            [],
        ),
    )
    for variant in ('gcc', 'buildv2'):
        if variant == 'buildv2':
            monkeypatch.setenv('IDF_BUILD_V2', '1')
            monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', 'buildv2')
        result = runner.invoke(click_cli, ['gitlab', 'build-child-pipeline', f'{variant}.yml'])
        assert result.exit_code == 0, result.output

    assert (tmp_path / 'test_related_apps.txt').is_file()
    assert (tmp_path / 'test_related_apps_buildv2.txt').is_file()
    assert (tmp_path / 'non_test_related_apps_buildv2.txt').is_file()
    monkeypatch.delenv('IDF_BUILD_V2')
    monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', 'gcc')
    result = runner.invoke(click_cli, ['gitlab', 'build-child-pipeline', 'explicit_gcc.yml'])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'test_related_apps_gcc.txt').is_file()
    assert (tmp_path / 'non_test_related_apps_gcc.txt').is_file()
    monkeypatch.setenv('CI', 'true')
    monkeypatch.setenv('IDF_TOOLCHAIN', 'gcc')
    _refresh_ci_settings()
    apps = preprocess_args().test_related_apps
    assert apps and apps[0].app_dir == 'examples/gcc'
    monkeypatch.setenv('IDF_CI_ARTIFACT_NAMESPACE', 'buildv2')
    apps = preprocess_args().test_related_apps
    assert apps and apps[0].app_dir == 'examples/buildv2'
    monkeypatch.delenv('IDF_CI_ARTIFACT_NAMESPACE')
    apps = preprocess_args().test_related_apps
    assert apps and apps[0].app_dir == 'examples/gcc'


def test_manifest_is_evaluated_again_for_each_toolchain(monkeypatch, tmp_path, runner):
    create_project('hello', tmp_path)
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(click_cli, ['build', 'init']).exit_code == 0
    (tmp_path / '.build-test-rules.yml').write_text(
        'hello:\n  disable:\n    - if: IDF_TOOLCHAIN == "clang"\n      reason: clang-disabled\n'
    )

    monkeypatch.setattr('idf_ci.idf_pytest.get_pytest_cases', lambda **kwargs: [])
    original_targets = DEFAULT_BUILD_TARGETS.get()
    DEFAULT_BUILD_TARGETS.set(['esp32'])
    try:
        _refresh_ci_settings(
            config_overrides={'gitlab': {'build_enabled_toolchains': ['gcc', 'clang'], 'test_enabled_toolchains': []}}
        )
        build_child_pipeline()
    finally:
        DEFAULT_BUILD_TARGETS.set(original_targets)

    gcc = CiSettings.read_apps_from_files(['non_test_related_apps.txt'])
    clang = CiSettings.read_apps_from_files(['non_test_related_apps_clang.txt'])
    assert gcc and gcc[0].target == 'esp32'
    assert clang == []
    assert 'fake_pass' in yaml.safe_load((tmp_path / 'build_child_pipeline_clang.yml').read_text())


def test_toolchain_config_rejects_invalid_or_unbuilt_test_variants():
    for build, test in [(['gcc'], ['clang']), (['gcc', '../clang'], []), (['gcc', 'gcc'], []), ([], [])]:
        with pytest.raises(ValidationError):
            CiSettings.model_validate(
                {
                    'gitlab': {
                        'build_enabled_toolchains': build,
                        'test_enabled_toolchains': test,
                    }
                }
            )


def test_toolchain_filename_keeps_parent_and_extension():
    assert Path(toolchain_filename('output/build.yml', 'gcc')) == Path('output/build.yml')
    assert Path(toolchain_filename('output/build.yml', 'clang')) == Path('output/build_clang.yml')
