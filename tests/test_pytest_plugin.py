# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

from conftest import create_project

from idf_ci.cli import cli


class TestPytestPlugin:
    def test_skip_tests_with_apps_not_built(self, pytester, runner):
        assert runner.invoke(cli, ['build', 'init', '--path', pytester.path]).exit_code == 0
        assert runner.invoke(cli, ['test', 'init', '--path', pytester.path]).exit_code == 0

        create_project('app1', pytester.path)
        create_project('app2', pytester.path)
        create_project('app3', pytester.path)

        pytester.maketxtfile(
            app_info_mock="""
            {"app_dir": "app1", "target": "esp32", "config_name": "default", "build_dir": "build_esp32_default", "build_system": "cmake", "build_status": "build success"}
            {"app_dir": "app2", "target": "esp32", "config_name": "default", "build_dir": "build_esp32_default", "build_system": "cmake", "build_status": "build success"}
            {"app_dir": "app3", "target": "esp32", "config_name": "default", "build_dir": "build_esp32_default", "build_system": "cmake", "build_status": "skipped"}
            """  # noqa: E501
        )

        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.parametrize('app_path', ['app1', 'app2', 'app3'], indirect=True)
                def test_skip_tests(dut):
                    assert True
            """)
        res = pytester.runpytest('--target', 'esp32', '--log-cli-level', 'DEBUG', '-s')
        res.assert_outcomes(errors=2)  # failed because of no real builds
