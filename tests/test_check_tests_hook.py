# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import create_project

from idf_ci.hooks.check_tests_missing_config import (
    main,
)


@pytest.mark.skipif(not os.getenv('IDF_PATH'), reason='IDF_PATH is not set')
class TestCheckTestsHookIntegration:
    def run(self, paths: list[str] | None = None):
        runner = CliRunner()
        result = runner.invoke(main, paths)
        return result

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

    def test_missing_config_detected(self, tmp_path: Path):
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

        result = self.run([str(tmp_path / 'foo' / 'test_hook_single.py')])

        assert result.exit_code == 1
        assert 'Sdkconfig file "release" is missing for test case "test_foo"' in result.output

    def test_missing_config_no_paths(self, tmp_path: Path):
        (tmp_path / 'foo' / 'test_hook_no_paths.py').write_text(
            textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize('config,target', [
                    ('release', 'esp32'),
                ], indirect=True)
                def test_foo(dut):
                    pass
            """)
        )

        result = self.run()

        assert result.exit_code == 1
        assert 'Sdkconfig file "release" is missing for test case "test_foo"' in result.output

    def test_missing_config_detected_multiple_tests(self, tmp_path: Path):
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

        result = self.run([str(tmp_path / 'foo' / 'test_hook_multiple.py')])

        assert result.exit_code == 1
        assert 'Sdkconfig file "release" is missing for test cases:' in result.output
        assert '\t\t- test_foo' in result.output
        assert '\t\t- test_bar' in result.output

    def test_no_error_when_config_exists(self, tmp_path: Path):
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

        result = self.run([str(tmp_path / 'foo' / 'test_hook_config_exists.py')])

        assert result.exit_code == 0
        assert result.output == ''
