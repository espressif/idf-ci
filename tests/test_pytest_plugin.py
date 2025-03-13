# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

from conftest import create_project

from idf_ci.cli import click_cli


class TestPytestPlugin:
    def test_skip_tests_with_apps_not_built(self, pytester, runner):
        assert runner.invoke(click_cli, ['build', 'init', '--path', pytester.path]).exit_code == 0
        assert runner.invoke(click_cli, ['test', 'init', '--path', pytester.path]).exit_code == 0

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

    def test_env_markers(self, pytester, runner):
        assert runner.invoke(click_cli, ['test', 'init', '--path', pytester.path]).exit_code == 0
        pytester.makepyfile("""
                import pytest
                from idf_ci.idf_pytest import PytestCase

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                def test_env_markers(dut):
                    assert PytestCase.KNOWN_ENV_MARKERS == {'foo', 'bar'}
            """)

        os.makedirs(pytester.path / 'build')
        pytester.makefile(
            '.ini',
            pytest="""
                [pytest]
                env_markers =
                    foo: foo
                    bar: bar
            """,
        )

        res = pytester.runpytest()
        res.assert_outcomes(passed=1)
