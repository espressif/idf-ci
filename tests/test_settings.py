# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import re

from idf_ci.cli import cli
from idf_ci.settings import CiSettings


def test_default_component_mapping_regexes():
    expected_regexes = [
        '/components/(.+)/',
        '/common_components/(.+)/',
    ]
    assert CiSettings().component_mapping_regexes == expected_regexes


def test_default_component_ignored_file_extensions():
    expected_extensions = [
        '.md',
        '.rst',
        '.yaml',
        '.yml',
        '.py',
    ]
    assert CiSettings().component_ignored_file_extensions == expected_extensions


def test_get_modified_components():
    test_files = [
        'components/wifi/wifi.c',
        'components/bt/bt_main.c',
        'common_components/esp_common/test.c',
        'docs/example.md',  # should be ignored
        'random/file.txt',  # should not match any component
    ]

    expected_components = {'wifi', 'bt', 'esp_common'}
    assert CiSettings().get_modified_components(test_files) == expected_components


def test_ignored_file_extensions():
    test_files = [
        'components/wifi/README.md',
        'components/bt/docs.rst',
        'components/esp_common/config.yaml',
        'components/test/test.yml',
        'components/utils/util.py',
    ]

    assert CiSettings().get_modified_components(test_files) == set()


def test_extended_component_mapping_regexes():
    settings = CiSettings(
        extend_component_mapping_regexes=[
            '/custom/path/(.+)/',
        ]
    )

    test_files = [
        'custom/path/my_component/test.c',
        'components/wifi/wifi.c',
    ]

    expected_components = {'my_component', 'wifi'}
    assert settings.get_modified_components(test_files) == expected_components


def test_extended_ignored_extensions():
    settings = CiSettings(
        extend_component_ignored_file_extensions=[
            '.txt',
            '.json',
        ]
    )

    test_files = [
        'components/wifi/test.txt',
        'components/bt/config.json',
        'components/esp_common/main.c',
    ]

    expected_components = {'esp_common'}
    assert settings.get_modified_components(test_files) == expected_components


def test_all_component_mapping_regexes():
    patterns = CiSettings().all_component_mapping_regexes
    assert len(patterns) == 2

    test_path = '/components/test_component/test.c'
    for pattern in patterns:
        match = pattern.search(test_path)
        if '/components/(.+)/' in pattern.pattern:
            assert match is not None
            assert match.group(1) == 'test_component'


def test_component_mapping_with_absolute_paths():
    abs_path = os.path.abspath('components/wifi/wifi.c')
    components = CiSettings().get_modified_components([abs_path])
    assert components == {'wifi'}


def test_ci_profile_option(tmp_path, runner):
    # Create a custom CI profile file
    custom_profile = tmp_path / 'custom_ci_profile.toml'
    with open(custom_profile, 'w') as f:
        f.write("""
extend_component_mapping_regexes = [
    '/custom/path/(.+)/'
]

component_ignored_file_extensions = [
    '.custom'
]
""")
    runner.invoke(cli, ['--ci-profile', custom_profile, 'build', 'init-profile'])
    runner.invoke(cli, ['--ci-profile', custom_profile, 'test', 'init-profile'])

    result = runner.invoke(cli, ['--ci-profile', custom_profile, 'build', 'run'])
    assert result.exit_code == 0
    assert f'Using CI profile: {custom_profile}' in result.output
    assert CiSettings.CONFIG_FILE_PATH == custom_profile
    assert len(CiSettings().all_component_mapping_regexes) == 3  # default got 2

    CiSettings.CONFIG_FILE_PATH = None  # reset

    # Test with non-existent profile
    non_existent = os.path.join(tmp_path, 'non_existent.toml')
    result = runner.invoke(cli, ['--ci-profile', non_existent])
    assert result.exit_code == 2  # Click returns 2 for parameter validation errors
    assert re.search(r"Error: Invalid value for '--ci-profile': File .* does not exist.", result.output)
    assert len(CiSettings().all_component_mapping_regexes) == 2  # default got 2


def test_ci_profile_not_specified(runner):
    original_config_path = CiSettings.CONFIG_FILE_PATH
    with runner.isolated_filesystem() as tmp_d:
        result = runner.invoke(cli, ['build', 'init-profile'])
        assert result.exit_code == 0
        assert CiSettings.CONFIG_FILE_PATH == original_config_path
        assert os.path.exists(tmp_d + os.sep + '.idf_build_apps.toml')
