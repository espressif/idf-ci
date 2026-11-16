# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os

import pytest
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


class TestDisableTestMarker:
    @pytest.fixture(autouse=True)
    def setup(self, pytester, runner):
        assert runner.invoke(click_cli, ['test', 'init', '--path', pytester.path]).exit_code == 0
        os.makedirs(pytester.path / 'build', exist_ok=True)

    def test_disabled_by_targets(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32', 'esp32c3'], indirect=True)
                @pytest.mark.disable_test(targets=['esp32c3'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'all', '--collect-only', '-q')
        # while collecting, disabled cases are kept so that the reports can list them
        res.assert_outcomes()
        assert res.ret == 0

        # 1 deselected by the marker, 1 by the target filter
        res = pytester.runpytest('--target', 'esp32c3')
        res.assert_outcomes(deselected=2)

        res = pytester.runpytest('--target', 'esp32')
        # selected, then fails because there is no build
        res.assert_outcomes(errors=1, deselected=1)

    def test_disabled_by_configs(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.parametrize('config', ['default', 'iram'], indirect=True)
                @pytest.mark.disable_test(configs=['iram'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32')
        res.assert_outcomes(errors=1, deselected=1)

    def test_disabled_by_expression(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32', 'esp32c3'], indirect=True)
                @pytest.mark.disable_test('IDF_TARGET == "esp32c3"', reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32c3')
        res.assert_outcomes(deselected=2)

        res = pytester.runpytest('--target', 'esp32')
        res.assert_outcomes(errors=1, deselected=1)

    def test_disabled_by_expression_and_configs(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.parametrize('config', ['default', 'iram'], indirect=True)
                @pytest.mark.disable_test('IDF_TARGET == "esp32"', configs=['iram'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32')
        res.assert_outcomes(errors=1, deselected=1)

    def test_multi_dut_any_app_matches(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('count', [2], indirect=True)
                @pytest.mark.parametrize('target', ['esp32|esp32c3'], indirect=True)
                @pytest.mark.disable_test(targets=['esp32c3'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32,esp32c3')
        res.assert_outcomes(deselected=1)

    def test_multi_dut_selector(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('count', [2], indirect=True)
                @pytest.mark.parametrize('target', ['esp32|esp32c3', 'esp32|esp32'], indirect=True)
                @pytest.mark.disable_test(targets=['esp32,esp32c3'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        # only the esp32+esp32c3 pair is disabled
        res = pytester.runpytest('--target', 'esp32,esp32c3')
        res.assert_outcomes(deselected=2)

        res = pytester.runpytest('--target', 'esp32,esp32')
        res.assert_outcomes(errors=1, deselected=1)

    def test_multi_dut_selector_with_wildcard(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('count', [2], indirect=True)
                @pytest.mark.parametrize('target', ['esp32|esp32c3', 'esp32c3|esp32'], indirect=True)
                @pytest.mark.disable_test(targets=['*,esp32c3'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        # only the pair whose second DUT is esp32c3 is disabled
        res = pytester.runpytest('--target', 'esp32,esp32c3')
        res.assert_outcomes(deselected=2)

        res = pytester.runpytest('--target', 'esp32c3,esp32')
        res.assert_outcomes(errors=1, deselected=1)

    def test_selector_does_not_match_single_dut(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.disable_test(targets=['esp32,*'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32')
        res.assert_outcomes(errors=1, deselected=0)

    def test_only_the_closest_marker_applies(self, pytester):
        pytester.makepyfile("""
                import pytest

                pytestmark = pytest.mark.disable_test(targets=['esp32c3'], reason='module level')

                @pytest.mark.parametrize('target', ['esp32', 'esp32c3', 'esp32s2'], indirect=True)
                @pytest.mark.disable_test('IDF_TARGET == "esp32s2"', reason='function level')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32s2')
        res.assert_outcomes(deselected=3)

        # the module-level marker is shadowed by the function-level one
        for target in ('esp32', 'esp32c3'):
            res = pytester.runpytest('--target', target)
            res.assert_outcomes(errors=1, deselected=2)

    def test_not_matching_marker_keeps_the_test(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.disable_test(targets=['esp32c3'], reason='IDF-1234')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32')
        res.assert_outcomes(errors=1, deselected=0)

    def test_invalid_marker_fails_collection(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.disable_test(reason='no condition at all')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32')
        assert res.ret != 0
        res.stderr.fnmatch_lines(['*`disable_test` marker is invalid*', '*at least one of*'])

    def test_invalid_marker_fails_collect_only(self, pytester):
        pytester.makepyfile("""
                import pytest

                @pytest.mark.parametrize('target', ['esp32'], indirect=True)
                @pytest.mark.disable_test('IDF_TARGET ==', reason='broken expression')
                def test_foo(dut):
                    pass
            """)

        res = pytester.runpytest('--target', 'esp32', '--collect-only')
        assert res.ret != 0
        res.stderr.fnmatch_lines(['*`disable_test` marker is invalid*failed to evaluate expression*'])
