# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

from idf_ci.cli import cli


def test_build_profile_init(runner, temp_dir):
    # Test init command with default path
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['build-profile', 'init', '--path', temp_dir])
        assert result.exit_code == 0
        assert f'Created build profile at {os.path.join(temp_dir, ".idf_build_apps.toml")}' in result.output
        assert os.path.exists(os.path.join(temp_dir, '.idf_build_apps.toml'))

    # Test init command with specific file path
    specific_path = os.path.join(temp_dir, 'custom_build.toml')
    result = runner.invoke(cli, ['build-profile', 'init', '--path', specific_path])
    assert result.exit_code == 0
    assert f'Created build profile at {specific_path}' in result.output
    assert os.path.exists(specific_path)


def test_ci_profile_init(runner, temp_dir):
    # Test init command with default path
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['ci-profile', 'init', '--path', temp_dir])
        assert result.exit_code == 0
        assert f'Created CI profile at {os.path.join(temp_dir, ".idf_ci.toml")}' in result.output
        assert os.path.exists(os.path.join(temp_dir, '.idf_ci.toml'))

    # Test init command with specific file path
    specific_path = os.path.join(temp_dir, 'custom_ci.toml')
    result = runner.invoke(cli, ['ci-profile', 'init', '--path', specific_path])
    assert result.exit_code == 0
    assert f'Created CI profile at {specific_path}' in result.output
    assert os.path.exists(specific_path)


def test_test_profile_init(runner, temp_dir):
    # Test init command with default path
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['test-profile', 'init', '--path', temp_dir])
        assert result.exit_code == 0
        assert f'Created test profile at {os.path.join(temp_dir, "pytest.ini")}' in result.output
        assert os.path.exists(os.path.join(temp_dir, 'pytest.ini'))

    # Test init command with specific file path
    specific_path = os.path.join(temp_dir, 'custom_test.toml')
    result = runner.invoke(cli, ['test-profile', 'init', '--path', specific_path])
    assert result.exit_code == 0
    assert f'Created test profile at {specific_path}' in result.output
    assert os.path.exists(specific_path)


def test_completions(runner):
    result = runner.invoke(cli, ['completions'])
    assert result.exit_code == 0
    assert 'To enable autocomplete run the following command:' in result.output
    assert 'Bash:' in result.output
    assert 'Zsh:' in result.output
    assert 'Fish:' in result.output


def test_profile_init_file_exists(runner, temp_dir):
    # Test that init doesn't fail if file already exists
    build_profile_path = os.path.join(temp_dir, '.idf_build_apps.toml')
    ci_profile_path = os.path.join(temp_dir, '.idf_ci.toml')

    # Create files first
    Path(build_profile_path).touch()
    Path(ci_profile_path).touch()

    # Try to init again
    result = runner.invoke(cli, ['build-profile', 'init', '--path', temp_dir])
    assert result.exit_code == 0

    result = runner.invoke(cli, ['ci-profile', 'init', '--path', temp_dir])
    assert result.exit_code == 0

    result = runner.invoke(cli, ['test-profile', 'init', '--path', temp_dir])
    assert result.exit_code == 0
