# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import importlib

import pytest
from esp_bool_parser import constants as bool_parser_constants

from idf_ci.filters import component_targets as ct


@pytest.fixture(autouse=True)
def patched_all_targets():
    original_targets = bool_parser_constants.ALL_TARGETS
    bool_parser_constants.ALL_TARGETS = ['esp32', 'esp32s2', 'esp32c3']
    importlib.reload(ct)
    ct.component_targets_from_files.cache_clear()

    try:
        yield
    finally:
        ct.component_targets_from_files.cache_clear()
        bool_parser_constants.ALL_TARGETS = original_targets
        importlib.reload(ct)


def test_component_targets_from_files_detects_targets_and_collapses_nested_folders():
    modified_files = (
        'components/foo/test_apps/esp32/main.c',
        'components/foo/test_apps/esp32/subdir/extra.c',
        'components/foo/test_apps/esp32s2/main.c',
        'components/bar/test_apps/esp32c3/main.c',
        'README.md',
        '',
        None,
    )

    assert ct.component_targets_from_files(modified_files) == {
        'bar': ['esp32c3'],
        'foo': ['esp32', 'esp32s2'],
    }


def test_component_targets_from_files_returns_all_for_component_root_changes():
    modified_files = (
        'components/foo/Kconfig',
        'components/foo/test_apps/esp32/main.c',
        'components/bar',
    )

    assert ct.component_targets_from_files(modified_files) == {
        'bar': ['all'],
        'foo': ['all'],
    }


def test_combined_targets_for_components_only_uses_requested_components():
    modified_files = (
        'components/foo/test_apps/esp32/main.c',
        'components/foo/test_apps/esp32s2/main.c',
        'components/bar/Kconfig',
    )

    assert ct.combined_targets_for_components(modified_files, ['foo']) == ['esp32', 'esp32s2']
    assert ct.combined_targets_for_components(modified_files, ['bar']) == ['all']
    assert ct.combined_targets_for_components(modified_files, ['missing']) == []
    assert ct.combined_targets_for_components(modified_files, []) == ['all']


@pytest.mark.parametrize(
    'modified_files,check_components,current_target,expected',
    [
        (('components/foo/test_apps/esp32/main.c',), ['foo'], 'esp32', False),
        (('components/foo/test_apps/esp32/main.c',), ['foo'], 'esp32c3', True),
        (('components/foo/Kconfig',), ['foo'], 'esp32c3', False),
        (('components/foo/test_apps/esp32/main.c',), ['missing'], 'esp32c3', False),
        (('components/foo/test_apps/esp32/main.c',), [], 'esp32c3', True),
        (('components/foo/test_apps/esp32/main.c', 'components/foo/test_apps/another/main.c'), [], 'esp32c3', False),
        ((), [], 'esp32c3', False),
        (('a/b/c',), [], 'esp32c3', False),
        (('a/b/c',), ['soc'], 'esp32c3', False),
    ],
)
def test_should_skip_build_for_components(modified_files, check_components, current_target, expected):
    assert ct.should_skip_build_for_components(modified_files, check_components, current_target) is expected
