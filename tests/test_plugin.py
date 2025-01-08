# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap

import pytest

from idf_ci import get_pytest_cases


class TestGetPytestCases:
    @pytest.fixture(autouse=True)
    def setup_test_scripts(self, tmp_path):
        original_dir = os.getcwd()
        os.chdir(tmp_path)

        test_script = tmp_path / f'pytest_{os.urandom(10).hex()}.py'

        test_script.write_text(
            textwrap.dedent("""
                import not_exists

                import os
                import tempfile
                import pytest

                @pytest.mark.parametrize('target, config', [
                    ('esp32s2', 'def_2'),
                    ('esp32s3', 'def_3'),
                ], indirect=True)
                def test_single_dut(dut, config):  # FIXME: config shall not be mandatory
                    pass

                @pytest.mark.parametrize('count, target', [
                    (2, 'esp32'),
                    (2, 'esp32s2|esp32s3'),
                ], indirect=True)
                def test_multi_dut(dut):
                    pass

                @pytest.mark.parametrize('count, app_path, target, config', [
                    (3, None, 'esp32s2', None),
                    (2, 'subdir', 'esp32s3', 'foo'),
                ], indirect=True)
                def test_multi_dut_with_custom_app_path(dut, config):  # FIXME: config shall not be mandatory
                    pass

                def test_no_param():
                    pass
                """)
        )

        yield

        os.chdir(original_dir)

    def test_collect_single_dut(self, temp_dir):
        cases = get_pytest_cases([temp_dir], 'esp32s2')
        assert len(cases) == 2
        assert cases[0].caseid == 'esp32s2.def_2.test_single_dut'
        assert cases[0].apps[0].build_dir == os.path.join(temp_dir, 'build_esp32s2_def_2')
        assert cases[1].caseid == 'esp32s2.default.test_no_param'

        cases = get_pytest_cases([temp_dir], 'esp32s3')
        assert len(cases) == 2
        assert cases[0].caseid == 'esp32s3.def_3.test_single_dut'
        assert cases[1].caseid == 'esp32s3.default.test_no_param'

    def test_collect_multi_dut(self, temp_dir):
        cases = get_pytest_cases([temp_dir], 'esp32,esp32')
        assert len(cases) == 1
        assert cases[0].caseid == "('esp32', 'esp32').('default', 'default').test_multi_dut"
        assert len(cases[0].apps) == 2
        assert cases[0].apps[0].build_dir == os.path.join(temp_dir, 'build_esp32_default')
        assert cases[0].apps[1].build_dir == os.path.join(temp_dir, 'build_esp32_default')

    def test_collect_multi_dut_with_custom_app_path(self, temp_dir):
        cases = get_pytest_cases([temp_dir], 'esp32s2,esp32s2,esp32s2')
        assert len(cases) == 1
        assert (
            cases[0].caseid
            == "('esp32s2', 'esp32s2', 'esp32s2').('default', 'default', 'default').test_multi_dut_with_custom_app_path"
        )
        assert cases[0].apps[0].build_dir == os.path.join(temp_dir, 'build_esp32s2_default')
        assert cases[0].apps[1].build_dir == os.path.join(temp_dir, 'build_esp32s2_default')
        assert cases[0].apps[2].build_dir == os.path.join(temp_dir, 'build_esp32s2_default')

        cases = get_pytest_cases([temp_dir], 'esp32s3,esp32s3')
        assert len(cases) == 1
        assert cases[0].caseid == "('esp32s3', 'esp32s3').('foo', 'foo').test_multi_dut_with_custom_app_path"
        assert cases[0].apps[0].build_dir == os.path.join(temp_dir, 'subdir', 'build_esp32s3_foo')
        assert cases[0].apps[1].build_dir == os.path.join(temp_dir, 'subdir', 'build_esp32s3_foo')
