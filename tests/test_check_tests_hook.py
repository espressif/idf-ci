# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap
from pathlib import Path

import pytest
from conftest import create_project

from idf_ci.hooks.check_tests_missing_config import (
    filter_redundant_tuple_configs,
    main,
    parse_config_from_caseid,
)


@pytest.mark.parametrize(
    'caseid,expected',
    [
        ('esp32.release.test_foo', 'release'),
        ("('esp32', 'esp32c3').('a', 'b').test_foo", ('a', 'b')),
        ("('esp32', 'esp32c3').('release', 'release').test_foo", 'release'),
        ("('esp32', 'esp32c3', 'esp32s3').('a', 'a', 'b').test_foo", ('a', 'b')),
        ("('esp32', 'esp32c3').('b', 'a').test_foo", ('a', 'b')),
    ],
)
def test_parse_config_from_caseid(caseid, expected):
    assert parse_config_from_caseid(caseid) == expected


@pytest.mark.parametrize(
    'input_map,expected',
    [
        (
            {'release': ['test1'], 'default': ['test2']},
            {'release': ['test1'], 'default': ['test2']},
        ),
        (
            {'release': ['test1'], ('default', 'release'): ['test2']},
            {'release': ['test1'], 'default': ['test2']},
        ),
        (
            {'a': ['test1'], 'b': ['test2'], ('a', 'b'): ['test3']},
            {'a': ['test1'], 'b': ['test2']},
        ),
        (
            {'release': ['test1'], ('a', 'b'): ['test2']},
            {'release': ['test1'], ('a', 'b'): ['test2']},
        ),
    ],
)
def test_filter_redundant_tuple_configs(input_map, expected):
    assert filter_redundant_tuple_configs(input_map) == expected


@pytest.mark.skipif(not os.getenv('IDF_PATH'), reason='IDF_PATH is not set')
class TestCheckTestsHookIntegration:
    @pytest.fixture(autouse=True)
    def setup_test_project(self, tmp_path: Path):
        create_project('foo', tmp_path)

        (tmp_path / '.idf_build_apps.toml').write_text(
            textwrap.dedent(f"""
                config = [
                    "sdkconfig.ci=default",
                    "sdkconfig.ci.*=",
                    "=default"
                ]

                check_manifest_rules = true
                manifest_rootpath = "{tmp_path.as_posix()}"
                manifest_filepatterns = [
                    '**/.build-test-rules.yml',
                ]
            """)
        )

    def test_missing_config_detected(self, tmp_path: Path, monkeypatch, capsys):
        (tmp_path / 'foo' / 'test_hook_single.py').write_text(
            textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize('config,target', [
                    ('release', 'esp32'),
                ], indirect=True)
                def test_foo(dut):
                    pass
            """)
        )

        monkeypatch.setattr('sys.argv', ['', (tmp_path / 'foo' / 'test_hook_single.py').as_posix()])
        ret = main()
        output = capsys.readouterr().out

        assert ret == 1
        assert 'Sdkconfig file "release" is missing for test case "test_foo"' in output

    def test_missing_config_detected_multiple_tests(self, tmp_path: Path, monkeypatch, capsys):
        (tmp_path / 'foo' / 'test_hook_multiple.py').write_text(
            textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize('config,target', [
                    ('release', 'esp32'),
                ], indirect=True)
                def test_foo(dut):
                    pass

                @pytest.mark.parametrize('config,target', [
                    ('release', 'esp32c3'),
                ], indirect=True)
                def test_bar(dut):
                    pass
            """)
        )

        monkeypatch.setattr('sys.argv', ['', (tmp_path / 'foo' / 'test_hook_multiple.py').as_posix()])
        ret = main()
        output = capsys.readouterr().out

        assert ret == 1
        assert 'Sdkconfig file "release" is missing for test cases:' in output
        assert '\t\t- test_foo' in output
        assert '\t\t- test_bar' in output

    def test_no_error_when_config_exists(self, tmp_path: Path, monkeypatch, capsys):
        (tmp_path / 'foo' / 'sdkconfig.ci.release').write_text('CONFIG_EXAMPLE=y\n')
        (tmp_path / 'foo' / 'test_hook_config_exists.py').write_text(
            textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize('config,target', [
                    ('release', 'esp32'),
                ], indirect=True)
                def test_foo(dut):
                    pass
            """)
        )

        monkeypatch.setattr('sys.argv', ['', (tmp_path / 'foo' / 'test_hook_config_exists.py').as_posix()])
        ret = main()
        output = capsys.readouterr().out

        assert ret == 0
        assert output == ''
