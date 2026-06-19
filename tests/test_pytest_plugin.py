# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
from xml.etree import ElementTree as ET

from conftest import create_project

from idf_ci.cli import click_cli
from idf_ci.settings import CiSettings


class TestPytestPlugin:
    def test_skip_tests_with_apps_not_built(self, pytester, runner, monkeypatch):
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
        # failed because of no real builds, and we don't check app collection files locally
        for env_key in CiSettings().ci_detection_envs:
            monkeypatch.delenv(env_key, raising=False)
        res = pytester.runpytest('--target', 'esp32', '--log-cli-level', 'DEBUG', '-s')
        res.assert_outcomes(errors=3)
        # failed because we have no builds for app3 according to the collection file when we're running in CI
        monkeypatch.setenv('CI', '1')
        res = pytester.runpytest('--target', 'esp32', '--log-cli-level', 'DEBUG', '-s')
        res.assert_outcomes(errors=2, deselected=1)

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


class TestPytestPluginJunitReport:
    def test_junit_report_uses_custom_test_case_name_for_setup_error_failure_and_pass(self, pytester):
        pytester.makefile(
            '.ini',
            pytest="""
                [pytest]
                junit_family = xunit1
            """,
        )
        pytester.makepyfile("""
            import pytest

            @pytest.fixture
            def broken_fixture():
                raise RuntimeError('setup boom')

            @pytest.mark.parametrize('target', ['esp32'], indirect=True)
            @pytest.mark.parametrize('config', ['debug'], indirect=True)
            def test_pass(target, config):
                assert True

            @pytest.mark.parametrize('target', ['esp32'], indirect=True)
            @pytest.mark.parametrize('config', ['debug'], indirect=True)
            def test_fail(target, config):
                assert False

            @pytest.mark.parametrize('target', ['esp32'], indirect=True)
            @pytest.mark.parametrize('config', ['debug'], indirect=True)
            def test_setup_error(target, config, broken_fixture):
                assert True
        """)
        os.makedirs(pytester.path / 'build_esp32_debug')

        report_path = pytester.path / 'report.xml'
        res = pytester.runpytest('--junitxml', str(report_path))

        res.assert_outcomes(passed=1, failed=1, errors=1)

        cases = {
            case.attrib['name']: case for case in ET.parse(report_path).findall('.//testcase') if 'name' in case.attrib
        }

        assert 'failure' not in {child.tag for child in cases['esp32.debug.test_pass']}
        assert 'error' not in {child.tag for child in cases['esp32.debug.test_pass']}
        assert 'failure' in {child.tag for child in cases['esp32.debug.test_fail']}
        assert 'error' in {child.tag for child in cases['esp32.debug.test_setup_error']}
