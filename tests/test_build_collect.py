# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import os
import textwrap
import typing as t
from pathlib import Path

import pytest
from conftest import create_project
from esp_bool_parser.constants import SUPPORTED_TARGETS

from idf_ci.cli import click_cli


def total_test_cases(data: dict) -> int:
    total = 0
    for _, apps in data.get('projects', {}).items():
        for app in apps:
            total += len(app.get('test_cases', []))
    return total


def match_app(data: dict, path: str, target: str, sdkconfig: str, cb: t.Callable[[t.Dict[str, t.Any]], bool]) -> bool:
    projects = data.get('projects', {})
    if path not in projects:
        return False

    for app in projects[path]:
        if app.get('target') != target or app.get('sdkconfig') != sdkconfig:
            continue

        if cb(app):
            return True

    return False


def has_test_case(data: dict, path: str, target: str, sdkconfig: str, test_case: str) -> bool:
    return match_app(
        data,
        path,
        target,
        sdkconfig,
        lambda app: test_case in app.get('test_cases', []),
    )


def check_property(data: dict, path: str, target: str, sdkconfig: str, property_name: str, property_value: str) -> bool:
    return match_app(
        data,
        path,
        target,
        sdkconfig,
        lambda app: app.get(property_name) == property_value,
    )


@pytest.mark.skipif(not os.getenv('IDF_PATH'), reason='IDF_PATH is not set')
class TestBuildCollect:
    @pytest.fixture(autouse=True)
    def setup_test_projects(self, tmp_path: Path):
        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

    def run_build_collect(self, tmp_path, runner) -> t.Dict[str, t.Any]:
        output_file = tmp_path / 'output.json'
        result = runner.invoke(
            click_cli,
            [
                'build',
                'collect',
                '--paths',
                str(tmp_path),
                '--output',
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as fr:
            data = json.load(fr)

        return data

    def test_build_collect_no_test_cases(self, tmp_path, runner) -> None:
        data = self.run_build_collect(tmp_path, runner)
        assert total_test_cases(data) == 0

    def test_build_collect_with_test_cases(self, tmp_path, runner) -> None:
        with open(tmp_path / 'foo' / 'test_foo1.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('target', [
                'esp32',
            ], indirect=True)
            def test_foo(dut):
                pass
            """)
            )

        with open(tmp_path / 'bar' / 'test_bar1.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('target', [
                'esp32', 'esp32c3',
            ], indirect=True)
            def test_bar(dut):
                pass
            """)
            )

        data = self.run_build_collect(tmp_path, runner)
        assert total_test_cases(data) == 3
        assert has_test_case(data, './foo', 'esp32', 'default', 'test_foo')
        assert has_test_case(data, './bar', 'esp32', 'default', 'test_bar')
        assert has_test_case(data, './bar', 'esp32c3', 'default', 'test_bar')

    def test_build_collect_with_sdkconfig(self, tmp_path, runner) -> None:
        with open(tmp_path / 'foo' / 'test_foo2.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('target', [
                'esp32',
            ], indirect=True)
            @pytest.mark.parametrize('config', [
                'cfg1', 'cfg2',
            ])
            def test_foo(dut):
                pass
            """)
            )

        with open(tmp_path / 'foo' / 'sdkconfig.ci.cfg1', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            CONFIG_EXAMPLE_OPTION=y
            """)
            )

        with open(tmp_path / 'foo' / 'sdkconfig.ci.cfg2', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            CONFIG_EXAMPLE_OPTION=y
            """)
            )

        with open(tmp_path / '.idf_build_apps.toml', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            config = [
                "sdkconfig.ci=default",
                "sdkconfig.*=",
                "=default"
            ]
            """)
            )

        data = self.run_build_collect(tmp_path, runner)
        assert total_test_cases(data) == 2
        assert has_test_case(data, './foo', 'esp32', 'cfg1', 'test_foo')
        assert has_test_case(data, './foo', 'esp32', 'cfg2', 'test_foo')

    def test_build_collect_include_disabled_apps(self, tmp_path, runner) -> None:
        with open(tmp_path / '.build-test-rules.yml', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            foo:
                disable:
                    - if: IDF_TARGET == "esp32"
                      reason: Disabled for esp32
            """)
            )

        with open(tmp_path / '.idf_build_apps.toml', 'w') as fw:
            fw.write(
                textwrap.dedent(f"""
            check_manifest_rules = true
            manifest_rootpath = "{tmp_path.as_posix()}"
            manifest_filepatterns = [
                '**/.build-test-rules.yml',
            ]
            """)
            )

        data = self.run_build_collect(tmp_path, runner)
        assert check_property(
            data,
            './foo',
            'esp32',
            'default',
            'build_status',
            'disabled',
        )

    def test_build_collect_supported_targets(self, tmp_path, runner) -> None:
        with open(tmp_path / 'foo' / 'test_foo3.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded_idf.utils import idf_parametrize

            @idf_parametrize('target', [
                ('supported_targets'),
            ], indirect=['target'])
            def test_foo(dut):
                pass
            """)
            )

        data = self.run_build_collect(tmp_path, runner)
        assert total_test_cases(data) == len(SUPPORTED_TARGETS)

    def test_build_collect_test_comment(self, tmp_path, runner) -> None:
        with open(tmp_path / '.build-test-rules.yml', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            foo:
                disable:
                    - if: IDF_TARGET == "esp32"
                      reason: Disabled for esp32
                disable_test:
                    - if: IDF_TARGET == "esp32c3"
                      reason: Disabled test for esp32c3
            """)
            )

        with open(tmp_path / '.idf_build_apps.toml', 'w') as fw:
            fw.write(
                textwrap.dedent(f"""
            check_manifest_rules = true
            manifest_rootpath = "{tmp_path.as_posix()}"
            manifest_filepatterns = [
                '**/.build-test-rules.yml',
            ]
            """)
            )

        data = self.run_build_collect(tmp_path, runner)

        # esp32
        assert check_property(
            data,
            './foo',
            'esp32',
            'default',
            'build_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled for esp32)',
        )

        assert check_property(
            data,
            './foo',
            'esp32',
            'default',
            'test_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled for esp32)',
        )

        # esp32c3
        assert check_property(
            data,
            './foo',
            'esp32c3',
            'default',
            'build_comment',
            '',
        )

        assert check_property(
            data,
            './foo',
            'esp32c3',
            'default',
            'test_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32c3" (reason: Disabled test for esp32c3)',
        )
