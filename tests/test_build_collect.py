# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import os
import textwrap
import typing as t
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from conftest import create_project
from esp_bool_parser.constants import SUPPORTED_TARGETS

from idf_ci.cli import click_cli


def match_app(data: dict, path: Path, target: str, sdkconfig: str, cb: t.Callable[[t.Dict[str, t.Any]], bool]) -> bool:
    projects = data.get('projects', {})
    normalized_path = Path(path).as_posix()
    project = None

    # Find project by path
    for project_path in projects:
        if Path(project_path).as_posix() == normalized_path:
            project = projects[project_path]
            break

    if project is None:
        return False

    for app in project.get('apps', []):
        if app.get('target') != target or app.get('sdkconfig') != sdkconfig:
            continue

        if cb(app):
            return True

    return False


def has_test_case(data: dict, path: Path, target: str, sdkconfig: str, test_case: str) -> bool:
    return match_app(
        data,
        path,
        target,
        sdkconfig,
        lambda app: any(tc.get('name') == test_case for tc in app.get('test_cases', [])),
    )


def has_test_case_by_caseid(data: dict, path: Path, target: str, sdkconfig: str, caseid: str) -> bool:
    return match_app(
        data,
        path,
        target,
        sdkconfig,
        lambda app: any(tc.get('caseid') == caseid for tc in app.get('test_cases', [])),
    )


def check_property(
    data: dict, path: Path, target: str, sdkconfig: str, property_name: str, property_value: t.Any
) -> bool:
    return match_app(
        data,
        path,
        target,
        sdkconfig,
        lambda app: app.get(property_name) == property_value,
    )


def check_test_case_property(
    data: dict, path: Path, target: str, sdkconfig: str, test_case: str, property_name: str, property_value: t.Any
) -> bool:
    return match_app(
        data,
        path,
        target,
        sdkconfig,
        lambda app: any(
            tc.get('name') == test_case and tc.get(property_name) == property_value for tc in app.get('test_cases', [])
        ),
    )


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

    def run_build_collect(
        self, root_path, runner, paths: t.Optional[t.List[Path]] = None, additional_args: t.Optional[t.List[str]] = None
    ) -> t.Dict[str, t.Any]:
        output_file = root_path / 'output.json'
        args = [
            'build',
            'collect',
            '--output',
            str(output_file),
        ]

        if paths is not None:
            for p in paths:
                args.extend(['--paths', str(p)])

        if additional_args is not None:
            args.extend(additional_args)

        result = runner.invoke(
            click_cli,
            args,
        )

        assert result.exit_code == 0
        assert output_file.exists()

        with open(output_file) as fr:
            data = json.load(fr)

        return data

    def test_build_collect_no_test_cases(self, tmp_path, runner) -> None:
        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases'] == 0

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
        assert data['summary']['total_test_cases_used'] == 3
        assert has_test_case(data, Path('foo'), 'esp32', 'default', 'test_foo')
        assert has_test_case(data, Path('bar'), 'esp32', 'default', 'test_bar')
        assert has_test_case(data, Path('bar'), 'esp32c3', 'default', 'test_bar')

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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases_used'] == 2
        assert has_test_case(data, Path('foo'), 'esp32', 'cfg1', 'test_foo')
        assert has_test_case(data, Path('foo'), 'esp32', 'cfg2', 'test_foo')

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

        data = self.run_build_collect(tmp_path, runner)
        assert check_property(
            data,
            Path('foo'),
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
        assert data['summary']['total_test_cases_used'] == len(SUPPORTED_TARGETS)

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

        data = self.run_build_collect(tmp_path, runner)

        # esp32
        assert check_property(
            data,
            Path('foo'),
            'esp32',
            'default',
            'build_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled for esp32)',
        )

        assert check_property(
            data,
            Path('foo'),
            'esp32',
            'default',
            'test_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled for esp32)',
        )

        # esp32c3
        assert check_property(
            data,
            Path('foo'),
            'esp32c3',
            'default',
            'build_comment',
            '',
        )

        assert check_property(
            data,
            Path('foo'),
            'esp32c3',
            'default',
            'test_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32c3" (reason: Disabled test for esp32c3)',
        )

    def test_build_collect_test_cases_requiring_nonexistent_app(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases_used'] == 1
        assert data['summary']['total_test_cases_requiring_nonexistent_app'] == 1

    def test_build_collect_multiple_targets(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases_used'] == 1
        assert data['summary']['total_test_cases_requiring_nonexistent_app'] == 0

    def test_build_collect_include_host_test(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases_used'] == 1
        assert has_test_case(data, Path('foo'), 'esp32', 'default', 'test_host')

    def test_build_collect_include_only_enabled_apps(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner, additional_args=['--include-only-enabled-apps'])
        assert data['summary']['total_test_cases_used'] == 1
        assert data['summary']['total_test_cases_requiring_nonexistent_app'] == 1
        assert has_test_case(data, Path('foo'), 'esp32c3', 'default', 'test_foo')
        assert not has_test_case(data, Path('foo'), 'esp32', 'default', 'test_foo')

    def test_build_collect_from_other_path(self, tmp_path, runner, monkeypatch) -> None:
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

        data = self.run_build_collect(other_path, runner, paths=[tmp_path / 'foo'])
        assert data['summary']['total_test_cases_used'] == 1
        assert has_test_case(data, (tmp_path / 'foo'), 'esp32', 'default', 'test_foo')

    def test_build_collect_temp_skip_ci_marker(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases'] == 4
        assert data['summary']['total_test_cases_used'] == 2
        assert data['summary']['total_test_cases_disabled'] == 2
        assert has_test_case(data, Path('foo'), 'esp32', 'default', 'test_foo1')
        assert has_test_case(data, Path('foo'), 'esp32', 'default', 'test_foo2')
        assert check_test_case_property(
            data,
            Path('foo'),
            'esp32c3',
            'default',
            'test_foo1',
            'disabled_by_marker',
            True,
        )
        assert check_test_case_property(
            data,
            Path('foo'),
            'esp32c3',
            'default',
            'test_foo1',
            'skip_reason',
            'Temporary skip for CI',
        )

    def test_build_collect_test_on_both_target_and_qemu(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases'] == 2
        assert data['summary']['total_test_cases_used'] == 2
        assert has_test_case_by_caseid(data, Path('foo'), 'esp32', 'default', 'esp32.default.test_foo')
        assert has_test_case_by_caseid(data, Path('foo'), 'esp32', 'default', 'esp32_qemu.default.test_foo')

    def test_build_collect_test_disabled_by_manifest(self, tmp_path, runner) -> None:
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

        data = self.run_build_collect(tmp_path, runner)
        assert data['summary']['total_test_cases'] == 2
        assert data['summary']['total_test_cases_used'] == 1
        assert data['summary']['total_test_cases_disabled'] == 1
        assert has_test_case(data, Path('foo'), 'esp32c3', 'default', 'test_foo')
        assert check_test_case_property(
            data,
            Path('foo'),
            'esp32',
            'default',
            'test_foo',
            'disabled_by_manifest',
            True,
        )
        assert check_test_case_property(
            data,
            Path('foo'),
            'esp32',
            'default',
            'test_foo',
            'test_comment',
            'Disabled by manifest rule: IDF_TARGET == "esp32" (reason: Disabled test for esp32)',
        )

    def test_build_collect_html_output(self, tmp_path, runner) -> None:
        output_file = tmp_path / 'output.html'

        args = [
            'build',
            'collect',
            '--format',
            'html',
            '--output',
            str(output_file),
        ]

        result = runner.invoke(
            click_cli,
            args,
        )

        assert result.exit_code == 0
        assert output_file.exists()
        with open(output_file) as fr:
            soup = BeautifulSoup(fr, 'html.parser')
            assert soup.find('html') is not None
