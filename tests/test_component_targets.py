# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import importlib
import os

import pytest
from esp_bool_parser import constants as bool_parser_constants

from idf_ci.filters import component_targets as ct
from idf_ci.settings import CiSettings


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


def _patch_settings(monkeypatch, **kwargs):
    monkeypatch.setattr(ct, 'get_ci_settings', lambda: CiSettings(**kwargs))
    ct.component_targets_from_files.cache_clear()


@pytest.mark.parametrize(
    'config_kwargs,modified_files,expected,make_absolute',
    [
        pytest.param(
            {},
            (
                'components/foo/esp32/main.c',
                'components/foo/esp32/subdir/extra.c',
                'components/foo/esp32s2/main.c',
                'components/bar/esp32c3/main.c',
                'components/bar/esp32c3/sub/ignored.c',
                'components/foo/test_apps/esp32/main.c',
                'components/bar/test_apps/esp32/main.c',
                'README.md',
                '',
                None,
            ),
            {
                'bar': ['esp32c3'],
                'foo': ['esp32', 'esp32s2'],
            },
            False,
            id='default-targets-collapse-nested-and-ignore-excluded',
        ),
        pytest.param(
            {},
            ('components/foo/test_apps/esp32/main.c',),
            {},
            False,
            id='excluded-paths-only',
        ),
        pytest.param(
            {},
            (
                'components/foo/test_apps/esp32/main.c',
                'components/foo/esp32s2/main.c',
                'components/bar/test_apps/esp32c3/main.c',
            ),
            {
                'foo': ['esp32s2'],
            },
            False,
            id='excluded-and-usual-paths-mixed',
        ),
        pytest.param(
            {},
            (
                'components/foo/Kconfig',
                'components/foo/test_apps/esp32/main.c',
                'components/bar',
            ),
            {
                'bar': ['all'],
                'foo': ['all'],
            },
            False,
            id='component-root-changes-return-all',
        ),
        pytest.param(
            {},
            (
                'components/foo/esp32/main.c',
                'components/foo/esp32s2/main.c',
            ),
            {
                'foo': ['esp32', 'esp32s2'],
            },
            True,
            id='absolute-path-inputs',
        ),
        pytest.param(
            {
                'extend_component_mapping_regexes': [
                    '/vendor_components/(.+?)/',
                ],
            },
            (
                'common_components/esp_common/esp32/main.c',
                'vendor_components/vendor_wifi/esp32s2/main.c',
                'vendor_components/vendor_wifi/esp32s2/sub/extra.c',
            ),
            {
                'esp_common': ['esp32'],
                'vendor_wifi': ['esp32s2'],
            },
            False,
            id='additional-component-mapping-roots',
        ),
        pytest.param(
            {
                'component_target_regexes': [
                    r'/targets/(linux|qemu)/',
                ],
            },
            (
                'components/foo/targets/linux/main.c',
                'components/foo/targets/qemu/sub/extra.c',
            ),
            {
                'foo': ['linux', 'qemu'],
            },
            False,
            id='configured-target-regexes',
        ),
    ],
)
def test_component_targets_from_files_examples(monkeypatch, config_kwargs, modified_files, expected, make_absolute):
    _patch_settings(monkeypatch, **config_kwargs)

    if make_absolute:
        modified_files = tuple(
            os.path.abspath(path) if isinstance(path, str) and path else path for path in modified_files
        )

    assert ct.component_targets_from_files(modified_files) == expected


def test_component_mapping_for_path_uses_all_component_mapping_regexes(monkeypatch):
    _patch_settings(
        monkeypatch,
        extend_component_mapping_regexes=[
            '/vendor_components/(.+?)/',
        ],
    )

    assert ct._component_mapping_for_path('components/foo/esp32/main.c') == (
        'foo',
        'components/foo',
        'components/foo/esp32/main.c',
    )
    assert ct._component_mapping_for_path('common_components/esp_common/test.c') == (
        'esp_common',
        'common_components/esp_common',
        'common_components/esp_common/test.c',
    )
    assert ct._component_mapping_for_path('vendor_components/vendor_wifi/esp32/main.c') == (
        'vendor_wifi',
        'vendor_components/vendor_wifi',
        'vendor_components/vendor_wifi/esp32/main.c',
    )
    assert ct._component_mapping_for_path('README.md') is None


def test_extract_targets_uses_configured_regexes(monkeypatch):
    _patch_settings(
        monkeypatch,
        component_target_regexes=[
            r'/targets/(linux|qemu)/',
        ],
    )

    assert ct.extract_targets('components/foo/targets/linux/main.c') == {'linux'}
    assert ct.extract_targets('components/foo/targets/linux/targets/qemu/main.c') == {'linux', 'qemu'}
    assert ct.extract_targets('components/foo/esp32/main.c') == set()


def test_combined_targets_for_components_only_uses_requested_components():
    modified_files = (
        'components/foo/esp32/main.c',
        'components/foo/esp32s2/main.c',
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
        (('components/foo/test_apps/esp32/main.c',), ['foo'], 'esp32c3', False),
        (('components/foo/Kconfig',), ['foo'], 'esp32c3', False),
        (('components/foo/test_apps/esp32/main.c',), ['missing'], 'esp32c3', False),
        (('components/foo/test_apps/esp32/main.c',), [], 'esp32c3', False),
        (('components/foo/test_apps/esp32/main.c', 'components/foo/test_apps/another/main.c'), [], 'esp32c3', False),
        ((), [], 'esp32c3', False),
        (('a/b/c',), [], 'esp32c3', False),
        (('a/b/c',), ['soc'], 'esp32c3', False),
        (('components/foo/esp32/main.c',), ['foo'], 'esp32', False),
        (('components/foo/esp32/main.c', 'components/foo/esp32s2/main.c'), ['foo'], 'esp32s2', False),
        (('components/foo/esp32/main.c', 'components/bar/esp32s2/main.c'), [], 'esp32s2', False),
        (('components/foo/esp32/main.c', 'components/bar/Kconfig'), ['bar'], 'esp32c3', False),
        (('common_components/esp_common/esp32/main.c',), ['esp_common'], 'esp32', False),
        (('components/foo/esp32/main.c',), ['foo'], 'esp32c3', True),
        (('components/foo/esp32/main.c',), [], 'esp32c3', True),
        (('components/foo/esp32/main.c', 'components/foo/esp32/subdir/extra.c'), ['foo'], 'esp32s2', True),
        (('components/foo/esp32/main.c', 'components/foo/esp32s2/main.c'), ['foo'], 'esp32c3', True),
        (('components/foo/esp32/main.c', 'components/bar/esp32s2/main.c'), [], 'esp32c3', True),
        (('components/foo/esp32/main.c', 'components/bar/esp32s2/main.c'), ['foo'], 'esp32s2', True),
        (('components/foo/esp32/main.c', 'components/bar/esp32s2/main.c'), ['bar'], 'esp32', True),
        (('components/foo/esp32/main.c', 'components/bar/Kconfig'), ['foo'], 'esp32c3', True),
        (('components/foo/esp32/main.c', 'a/b/c'), [], 'esp32c3', True),
        (('common_components/esp_common/esp32/main.c',), ['esp_common'], 'esp32c3', True),
    ],
)
def test_should_skip_build_for_components(modified_files, check_components, current_target, expected):
    assert ct.should_skip_build_for_components(modified_files, check_components, current_target) is expected
