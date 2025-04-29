# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import textwrap
from pathlib import Path

import pytest

from idf_ci import get_pytest_cases
from idf_ci.cli import click_cli


class TestGetPytestCases:
    @pytest.fixture(autouse=True)
    def _setup(self, runner):
        assert runner.invoke(click_cli, ['test', 'init']).exit_code == 0

        yield

    TEMPLATE_SCRIPT = textwrap.dedent("""
        import pytest

        @pytest.mark.parametrize('target', [
            'esp32',
            'esp32c3',
        ], indirect=True)
        def test_foo_single(dut):
            pass

        @pytest.mark.parametrize('count,target', [
            (2, 'esp32|esp32s2'),
            (3, 'esp32s2|esp32s2|esp32s3'),
        ], indirect=True)
        def test_foo_multi(dut):
            pass

        @pytest.mark.parametrize('target', [
            'linux',
        ], indirect=True)
        def test_foo_host(dut):
            pass

        @pytest.mark.parametrize('target', [
            'esp32',
        ], indirect=True)
        @pytest.mark.qemu
        def test_foo_qemu(dut):
            pass
        """)

    def test_get_single_specific(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_get_single_specific.py'
        script.write_text(self.TEMPLATE_SCRIPT)
        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32')

        assert len(cases) == 1
        assert cases[0].targets == ['esp32']
        assert cases[0].name == 'test_foo_single'

    def test_get_multi_specific(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_get_multi_specific.py'
        script.write_text(self.TEMPLATE_SCRIPT)
        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32s2,esp32s2,esp32s3')

        assert len(cases) == 1
        assert cases[0].targets == ['esp32s2', 'esp32s2', 'esp32s3']
        assert cases[0].name == 'test_foo_multi'

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32s3,esp32s2,esp32s2')  # order matters
        assert len(cases) == 0

    def test_get_by_filter(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_get_by_filter.py'
        script.write_text(self.TEMPLATE_SCRIPT)
        cases = get_pytest_cases(paths=[str(tmp_path)], target='linux', filter_expr='foo')

        assert len(cases) == 1
        assert cases[0].name == 'test_foo_host'

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32', filter_expr='foo')
        assert len(cases) == 1
        assert cases[0].name == 'test_foo_single'

    def test_get_all(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_get_multi_all.py'
        script.write_text(self.TEMPLATE_SCRIPT)
        cases = get_pytest_cases(paths=[str(tmp_path)])

        assert len(cases) == 4
        assert cases[0].name == 'test_foo_single'
        assert cases[0].targets == ['esp32']

        assert cases[1].name == 'test_foo_single'
        assert cases[1].targets == ['esp32c3']

        assert cases[2].name == 'test_foo_multi'
        assert cases[2].targets == ['esp32', 'esp32s2']

        assert cases[3].name == 'test_foo_multi'
        assert cases[3].targets == ['esp32s2', 'esp32s2', 'esp32s3']

    def test_filter_with_sdkconfig_name(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_filter_with_sdkconfig_name.py'
        script.write_text(
            textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('config,target', [
                ('foo', 'esp32'),
                ('bar', 'esp32'),
            ], indirect=True)
            def test_filter_with_sdkconfig_name_single_dut(dut, config):
                pass

            @pytest.mark.parametrize('count', [2], indirect=True)
            @pytest.mark.parametrize('config,target', [
                ('foo|bar', 'esp32'),
                ('bar|baz', 'esp32'),
            ], indirect=True)
            def test_filter_with_sdkconfig_name_multi_dut(dut, config):
                pass
            """)
        )

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32', sdkconfig_name='foo')
        assert len(cases) == 1
        assert cases[0].caseid == 'esp32.foo.test_filter_with_sdkconfig_name_single_dut'
        assert cases[0].apps[0].build_dir == str(tmp_path / 'build_esp32_foo')

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32,esp32', sdkconfig_name='foo')
        assert len(cases) == 1

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32,esp32', sdkconfig_name='bar')
        assert len(cases) == 2

    def test_host_test(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_host_test.py'
        script.write_text(self.TEMPLATE_SCRIPT)

        cases = get_pytest_cases(paths=[str(tmp_path)], target='linux')
        assert len(cases) == 1
        assert cases[0].name == 'test_foo_host'

        cases = get_pytest_cases(paths=[str(tmp_path)], target='all', marker_expr='host_test')
        assert len(cases) == 2
        assert cases[0].name == 'test_foo_host'
        assert cases[1].name == 'test_foo_qemu'

    def test_custom_app_path(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_custom_app_path.py'
        script.write_text(
            textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('count, app_path, target, config', [
                (3, None, 'esp32s2', None),
                (2, 'subdir', 'esp32s3', 'foo'),
            ], indirect=True)
            def test_multi_dut_with_custom_app_path(dut, config):
                pass
            """)
        )

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32s3,esp32s3')
        assert len(cases) == 1
        assert cases[0].caseid == "('esp32s3', 'esp32s3').('foo', 'foo').test_multi_dut_with_custom_app_path"
        assert cases[0].apps[0].build_dir == str(tmp_path / 'subdir' / 'build_esp32s3_foo')
        assert cases[0].apps[1].build_dir == str(tmp_path / 'subdir' / 'build_esp32s3_foo')

    def test_no_params(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_no_params.py'
        script.write_text(
            textwrap.dedent("""
            def test_no_param():
                pass
            """)
        )

        cases = get_pytest_cases(paths=[str(tmp_path)])
        assert len(cases) == 0  # since target is required

    def test_qemu_caseid(self, tmp_path: Path) -> None:
        script = tmp_path / 'test_qemu_caseid.py'
        script.write_text(self.TEMPLATE_SCRIPT)

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32', marker_expr='qemu')
        assert len(cases) == 1
        assert cases[0].name == 'test_foo_qemu'
        assert cases[0].caseid == 'esp32_qemu.default.test_foo_qemu'

        cases = get_pytest_cases(paths=[str(tmp_path)], target='esp32')
        assert len(cases) == 1
        assert cases[0].name == 'test_foo_single'
        assert cases[0].caseid == 'esp32.default.test_foo_single'
