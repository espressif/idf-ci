# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

import pytest

from idf_ci.settings import CiSettings


@pytest.fixture
def default_settings():
    return CiSettings()


def test_default_component_mapping_regexes(default_settings):
    expected_regexes = [
        '/components/(.+)/',
        '/common_components/(.+)/',
    ]
    assert default_settings.component_mapping_regexes == expected_regexes


def test_default_component_ignored_file_extensions(default_settings):
    expected_extensions = [
        '.md',
        '.rst',
        '.yaml',
        '.yml',
        '.py',
    ]
    assert default_settings.component_ignored_file_extensions == expected_extensions


def test_get_modified_components(default_settings):
    test_files = [
        'components/wifi/wifi.c',
        'components/bt/bt_main.c',
        'common_components/esp_common/test.c',
        'docs/example.md',  # should be ignored
        'random/file.txt',  # should not match any component
    ]

    expected_components = {'wifi', 'bt', 'esp_common'}
    assert default_settings.get_modified_components(test_files) == expected_components


def test_ignored_file_extensions(default_settings):
    test_files = [
        'components/wifi/README.md',
        'components/bt/docs.rst',
        'components/esp_common/config.yaml',
        'components/test/test.yml',
        'components/utils/util.py',
    ]

    assert default_settings.get_modified_components(test_files) == set()


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


def test_build_profile_default():
    settings = CiSettings()
    assert settings.build_profile == 'default'


def test_build_profile_custom():
    custom_profile = 'custom_profile'
    settings = CiSettings(build_profile=custom_profile)
    assert settings.build_profile == custom_profile


def test_all_component_mapping_regexes(default_settings):
    patterns = default_settings.all_component_mapping_regexes
    assert len(patterns) == 2

    test_path = '/components/test_component/test.c'
    for pattern in patterns:
        match = pattern.search(test_path)
        if '/components/(.+)/' in pattern.pattern:
            assert match is not None
            assert match.group(1) == 'test_component'


def test_component_mapping_with_absolute_paths(default_settings):
    abs_path = os.path.abspath('components/wifi/wifi.c')
    components = default_settings.get_modified_components([abs_path])
    assert components == {'wifi'}
