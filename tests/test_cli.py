# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

import pytest

from idf_ci.cli import click_cli


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
