# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

import pytest

from idf_ci.cli import click_cli
from idf_ci.settings import CiSettings


@pytest.mark.parametrize(
    'command, default_file, specific_file',
    [
        (['build', 'init'], '.idf_build_apps.toml', 'custom_build.toml'),
        (['init'], '.idf_ci.toml', 'custom_ci.toml'),
        (['test', 'init'], 'pytest.ini', 'custom_test.ini'),
    ],
)
def test_init_commands(runner, tmp_dir, command, default_file, specific_file):
    # Test init command with default path
    with runner.isolated_filesystem():
        result = runner.invoke(click_cli, [*command, '--path', tmp_dir])
        assert result.exit_code == 0
        assert f'Created {os.path.join(tmp_dir, default_file)}' in result.output
        assert os.path.exists(os.path.join(tmp_dir, default_file))

    # Test init command with specific file path
    specific_path = os.path.join(tmp_dir, specific_file)
    result = runner.invoke(click_cli, [*command, '--path', specific_path])
    assert result.exit_code == 0
    assert f'Created {specific_path}' in result.output
    assert os.path.exists(specific_path)


def test_completions(runner):
    result = runner.invoke(click_cli, ['completions'])
    assert result.exit_code == 0
    assert 'To enable autocomplete run the following command:' in result.output
    assert 'Bash:' in result.output
    assert 'Zsh:' in result.output
    assert 'Fish:' in result.output


def test_init_but_already_exists(runner, tmp_dir):
    build_profile_path = os.path.join(tmp_dir, '.idf_build_apps.toml')
    ci_profile_path = os.path.join(tmp_dir, '.idf_ci.toml')

    # Create files first
    Path(build_profile_path).touch()
    Path(ci_profile_path).touch()

    # Try to init again
    result = runner.invoke(click_cli, ['build', 'init', '--path', tmp_dir])
    assert result.exit_code == 0

    result = runner.invoke(click_cli, ['init', '--path', tmp_dir])
    assert result.exit_code == 0

    result = runner.invoke(click_cli, ['test', 'init', '--path', tmp_dir])
    assert result.exit_code == 0


class TestConfig:
    @pytest.fixture(autouse=True)
    def _setup_method(self):
        CiSettings.CLI_OVERRIDES = {}

    @pytest.fixture(autouse=True)
    def _teardown_method(self):
        CiSettings.CLI_OVERRIDES = {}

    def test_config_nested_assignment_with_spaces(self, runner):
        result = runner.invoke(
            click_cli,
            ['--config', 'gitlab.build_pipeline.runs_per_job = 10', 'completions'],
        )
        assert result.exit_code == 0

        settings = CiSettings()
        assert settings.gitlab.build_pipeline.runs_per_job == 10

    def test_config_multiple_overrides_merged(self, runner):
        result = runner.invoke(
            click_cli,
            [
                '--config',
                'gitlab.build_pipeline.runs_per_job=10',
                '--config',
                'gitlab.build_pipeline.workflow_name="A"',
                'completions',
            ],
        )
        assert result.exit_code == 0

        settings = CiSettings()
        assert settings.gitlab.build_pipeline.runs_per_job == 10
        assert settings.gitlab.build_pipeline.workflow_name == 'A'

    def test_config_invalid_value_errors(self, runner):
        result = runner.invoke(
            click_cli,
            ['--config', 'gitlab.build_pipeline.runs_per_job = not_a_literal', 'completions'],
        )
        assert result.exit_code != 0
        assert 'Failed to parse value in --config `gitlab.build_pipeline.runs_per_job = not_a_literal`' in result.output

    def test_config_invalid_format_errors(self, runner):
        result = runner.invoke(click_cli, ['--config', 'abc', 'completions'])
        assert result.exit_code != 0
        assert 'Invalid --config entry `abc`' in result.output

    def test_config_empty_key_errors(self, runner):
        result = runner.invoke(click_cli, ['--config', ' = 1', 'completions'])
        assert result.exit_code != 0
        assert 'Empty key in --config assignment' in result.output
