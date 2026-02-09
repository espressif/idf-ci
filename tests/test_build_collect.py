# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap
import typing as t
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from conftest import create_project
from esp_bool_parser.constants import SUPPORTED_TARGETS
from idf_build_apps.constants import BuildStatus

from idf_ci.build_collect.models import AppInfo, CaseInfo, CollectResult, MissingAppInfo, ProjectInfo
from idf_ci.build_collect.scripts import collect_apps, format_as_html


def find_project(result: CollectResult, path: Path) -> t.Optional[ProjectInfo]:
    for project_path in result.projects.keys():
        if Path(project_path) == path:
            return result.projects[project_path]
    return None


def find_app(result: CollectResult, path: Path, target: str, config: str) -> t.Optional[AppInfo]:
    project = find_project(result, path)
    if project is None:
        return None

    for app in project.apps:
        if app.target == target and app.config == config:
            return app
    return None


def find_missing_app(result: CollectResult, path: Path, target: str, config: str) -> t.Optional[MissingAppInfo]:
    project = find_project(result, path)
    if project is None:
        return None

    for app in project.missing_apps:
        if app.target == target and app.config == config:
            return app
    return None


def find_test_case(result: CollectResult, path: Path, target: str, config: str, caseid: str) -> t.Optional[CaseInfo]:
    app = find_app(result, path, target, config)
    if app is None:
        return None

    for test_case in app.test_cases:
        if test_case.caseid == caseid:
            return test_case

    return None


def find_missing_test_case(
    result: CollectResult, path: Path, target: str, config: str, caseid: str
) -> t.Optional[CaseInfo]:
    missing_app = find_missing_app(result, path, target, config)
    if missing_app is None:
        return None

    for test_case in missing_app.test_cases:
        if test_case.caseid == caseid:
            return test_case
    return None


@pytest.mark.skipif(not os.getenv('IDF_PATH'), reason='IDF_PATH is not set')
class TestBuildCollect:
    @pytest.fixture(autouse=True)
    def setup_test_projects(self, tmp_path: Path):
        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

        with open(tmp_path / '.idf_build_apps.toml', 'w') as fw:
            fw.write(
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

    def test_build_collect_no_test_cases(self) -> None:
        result = collect_apps()
        assert result.summary.total_test_cases == 0

    def test_build_collect_with_test_cases(self, tmp_path) -> None:
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

        result = collect_apps()
        assert result.summary.total_test_cases == 3
        assert find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo')
        assert find_test_case(result, Path('bar'), 'esp32', 'default', 'esp32.default.test_bar')
        assert find_test_case(result, Path('bar'), 'esp32c3', 'default', 'esp32c3.default.test_bar')

    def test_build_collect_with_sdkconfig(self, tmp_path) -> None:
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

        result = collect_apps()
        assert result.summary.total_test_cases == 2
        assert find_test_case(result, Path('foo'), 'esp32', 'cfg1', 'esp32.cfg1.test_foo')
        assert find_test_case(result, Path('foo'), 'esp32', 'cfg2', 'esp32.cfg2.test_foo')

    def test_build_collect_include_disabled_apps(self, tmp_path) -> None:
        with open(tmp_path / '.build-test-rules.yml', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            foo:
                disable:
                    - if: IDF_TARGET == "esp32"
                      reason: Disabled for esp32
            """)
            )

        result = collect_apps()
        app = find_app(result, Path('foo'), 'esp32', 'default')
        assert app and app.build_status == BuildStatus.DISABLED

    def test_build_collect_supported_targets(self, tmp_path) -> None:
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

        result = collect_apps()
        assert result.summary.total_test_cases == len(SUPPORTED_TARGETS)

    def test_build_collect_test_comment(self, tmp_path) -> None:
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

        result = collect_apps()

        # esp32
        app_esp32 = find_app(result, Path('foo'), 'esp32', 'default')
        assert app_esp32 is not None
        assert (
            app_esp32.build_comment == 'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled for esp32)'
        )
        assert app_esp32.test_comment == 'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled for esp32)'

        # esp32c3
        app_esp32c3 = find_app(result, Path('foo'), 'esp32c3', 'default')
        assert app_esp32c3 is not None
        assert app_esp32c3.build_comment == ''
        assert (
            app_esp32c3.test_comment
            == 'Disabled by manifest rule: IDF_TARGET == "esp32c3" (reason: Disabled test for esp32c3)'
        )

    def test_build_collect_test_cases_missing_app(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo4.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('config, target', [
                ('default', 'esp32'),
            ], indirect=True)
            def test_foo(dut):
                pass

            @pytest.mark.parametrize('config, target', [
                ('release', 'esp32')
            ], indirect=True)
            def test_bar(dut):
                pass
            """)
            )

        with open(tmp_path / 'foo' / 'sdkconfig.ci.release', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            CONFIG_EXAMPLE_OPTION=y
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 2
        assert result.summary.total_test_cases_used == 1
        assert result.summary.total_test_cases_missing_app == 1
        assert find_test_case(result, Path('foo'), 'esp32', 'release', 'esp32.release.test_bar')
        assert find_missing_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo')

    def test_build_collect_multiple_targets(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo5.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded_idf.utils import idf_parametrize

            @pytest.mark.generic_multi_device
            @pytest.mark.parametrize(
                'count, config',
                [
                    (2, 'release'),
                ],
                indirect=True,
            )
            @idf_parametrize('target', ['esp32'], indirect=['target'])
            def test_ledc_multi_device(case_tester) -> None:  # type: ignore
                case_tester.run_all_multi_dev_cases(reset=True)
            """)
            )

        with open(tmp_path / 'foo' / 'sdkconfig.ci.release', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            CONFIG_EXAMPLE_OPTION=y
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 1
        assert result.summary.total_test_cases_used == 1
        assert result.summary.total_test_cases_missing_app == 0
        assert find_test_case(
            result, Path('foo'), 'esp32', 'release', "('esp32', 'esp32').('release', 'release').test_ledc_multi_device"
        )

    def test_build_collect_include_host_test(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo6.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded_idf.utils import idf_parametrize

            @pytest.mark.host_test
            @idf_parametrize('target', ['esp32'], indirect=['target'])
            def test_host(dut):
                pass
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases_used == 1
        assert find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_host')

    def test_build_collect_include_only_enabled_apps(self, tmp_path) -> None:
        with open(tmp_path / '.build-test-rules.yml', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            foo:
                disable:
                    - if: IDF_TARGET == "esp32"
                      reason: Disabled for esp32
            """)
            )

        with open(tmp_path / 'foo' / 'test_foo7.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded_idf.utils import idf_parametrize

            @idf_parametrize('target', ['esp32', 'esp32c3'], indirect=['target'])
            def test_foo(dut):
                pass
            """)
            )

        result = collect_apps(include_only_enabled=True)
        assert result.summary.total_test_cases_used == 1
        assert result.summary.total_test_cases_missing_app == 1
        assert find_test_case(result, Path('foo'), 'esp32c3', 'default', 'esp32c3.default.test_foo')
        assert find_missing_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo')

    def test_build_collect_use_other_path(self, tmp_path, monkeypatch) -> None:
        with open(tmp_path / 'foo' / 'test_foo8.py', 'w') as fw:
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

        other_path = tmp_path / 'baz'
        os.makedirs(other_path)
        monkeypatch.chdir(other_path)

        result = collect_apps(paths=[tmp_path / 'foo'])
        assert result.summary.total_test_cases_used == 1
        assert find_test_case(result, (tmp_path / 'foo'), 'esp32', 'default', 'esp32.default.test_foo')

    def test_build_collect_temp_skip_ci_marker(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo9.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('target', ['esp32', 'esp32c3'], indirect=True)
            @pytest.mark.temp_skip_ci(targets=['esp32c3'], reason='Temporary skip for CI')
            def test_foo1(dut):
                pass

            @pytest.mark.parametrize('target', ['esp32', 'esp32c3'], indirect=True)
            @pytest.mark.temp_skip(targets=['esp32c3'], reason='Temporary skip for CI')
            def test_foo2(dut):
                pass
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 4
        assert result.summary.total_test_cases_used == 2
        assert result.summary.total_test_cases_disabled == 2
        assert find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo1')
        assert find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo2')

        test_case = find_test_case(result, Path('foo'), 'esp32c3', 'default', 'esp32c3.default.test_foo1')
        assert test_case is not None
        assert test_case.disabled_by_marker
        assert test_case.skip_reason == 'Temporary skip for CI'

    def test_build_collect_test_on_both_target_and_qemu(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo10.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded import Dut
            from pytest_embedded_idf.utils import idf_parametrize

            @idf_parametrize(
                'target,test_on,markers',
                [
                    ('esp32', 'target', (pytest.mark.generic)),
                    ('esp32', 'qemu', (pytest.mark.host_test, pytest.mark.qemu))
                ],
                indirect=['target']
            )
            def test_foo(dut: Dut, test_on: str) -> None:
                pass
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 2
        assert result.summary.total_test_cases_used == 2
        assert find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo')
        assert find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32_qemu.default.test_foo')

    def test_build_collect_test_disabled_by_manifest(self, tmp_path) -> None:
        with open(tmp_path / '.build-test-rules.yml', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            foo:
                disable_test:
                    - if: IDF_TARGET == "esp32"
                      reason: Disabled test for esp32
            """)
            )

        with open(tmp_path / 'foo' / 'test_foo11.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded_idf.utils import idf_parametrize

            @idf_parametrize('target', ['esp32', 'esp32c3'], indirect=['target'])
            def test_foo(dut):
                pass
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 2
        assert result.summary.total_test_cases_used == 1
        assert result.summary.total_test_cases_disabled == 1
        assert find_test_case(result, Path('foo'), 'esp32c3', 'default', 'esp32c3.default.test_foo')

        test_case = find_test_case(result, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo')
        assert test_case is not None
        assert test_case.disabled_by_manifest
        assert (
            test_case.test_comment
            == 'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled test for esp32)'
        )

    def test_build_collect_multiple_configs_one_missing(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo12.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded import Dut

            @pytest.mark.two_duts
            @pytest.mark.parametrize(
                'count, target, config',
                [
                    (2, 'esp32', 'cfg1|cfg2'),
                ],
                indirect=True,
            )
            def test_foo(dut) -> None:
                pass
            """)
            )

        with open(tmp_path / 'foo' / 'sdkconfig.ci.cfg1', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            CONFIG_EXAMPLE_OPTION=y
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 1
        assert result.summary.total_test_cases_used == 1
        assert result.summary.total_test_cases_missing_app == 1
        assert find_test_case(result, Path('foo'), 'esp32', 'cfg1', "('esp32', 'esp32').('cfg1', 'cfg2').test_foo")
        assert find_missing_test_case(
            result, Path('foo'), 'esp32', 'cfg2', "('esp32', 'esp32').('cfg1', 'cfg2').test_foo"
        )

    def test_build_collect_multiple_configs_all_missing(self, tmp_path) -> None:
        with open(tmp_path / 'foo' / 'test_foo13.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest
            from pytest_embedded import Dut

            @pytest.mark.two_duts
            @pytest.mark.parametrize(
                'count, target, config',
                [
                    (2, 'esp32', 'cfg1|cfg2'),
                ],
                indirect=True,
            )
            def test_foo(dut) -> None:
                pass
            """)
            )

        result = collect_apps()
        assert result.summary.total_test_cases == 1
        assert result.summary.total_test_cases_used == 0
        assert result.summary.total_test_cases_missing_app == 1
        assert find_missing_test_case(
            result, Path('foo'), 'esp32', 'cfg1', "('esp32', 'esp32').('cfg1', 'cfg2').test_foo"
        )
        assert find_missing_test_case(
            result, Path('foo'), 'esp32', 'cfg2', "('esp32', 'esp32').('cfg1', 'cfg2').test_foo"
        )

    def test_build_collect_html_output(self) -> None:
        result = collect_apps()
        html_output = format_as_html(result)

        soup = BeautifulSoup(html_output, 'html.parser')
        assert soup.find('html') is not None
