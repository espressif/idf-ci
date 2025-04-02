# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
import textwrap
from pathlib import Path

import pytest
from conftest import create_project
from idf_build_apps import CMakeApp
from idf_build_apps.constants import SUPPORTED_TARGETS, BuildStatus

from idf_ci import CiSettings, get_all_apps
from idf_ci.cli import click_cli
from idf_ci.idf_gitlab.pipeline import dump_apps_to_txt


@pytest.mark.skipif(os.getenv('IDF_PATH') is None, reason='IDF_PATH is set')
class TestGetAllApps:
    @pytest.fixture(autouse=True)
    def _setup(self, runner):
        assert runner.invoke(click_cli, ['build', 'init']).exit_code == 0
        assert runner.invoke(click_cli, ['test', 'init']).exit_code == 0

        yield

    def test_without_test_scripts(self, tmp_path: Path) -> None:
        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)])

        assert len(test_related_apps) == 0
        assert len(non_test_related_apps) == 2 * len(SUPPORTED_TARGETS)
        assert SUPPORTED_TARGETS == [
            'esp32',
            'esp32s2',
            'esp32c3',
            'esp32s3',
            'esp32c2',
            'esp32c6',
            'esp32h2',
            'esp32p4',
        ]

    def test_single_dut_test_script(self, tmp_path: Path) -> None:
        create_project('foo', tmp_path)
        with open(tmp_path / 'foo' / 'test_single_dut_test_script.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize('target', [
                    'esp32',
                    'esp32s2',
                ], indirect=True)
                def test_foo(dut):
                    pass
                """)
            )
        create_project('bar', tmp_path)

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')

        assert len(test_related_apps) == 2
        assert len(non_test_related_apps) == 2 * len(SUPPORTED_TARGETS) - 2

    def test_multi_dut_test_script(self, tmp_path: Path) -> None:
        create_project('foo', tmp_path)
        with open(tmp_path / 'foo' / 'test_multi_dut_test_script.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize(
                    'count, target', [
                        (2, 'esp32s2|esp32s3'),
                        (3, 'esp32|esp32s3|esp32'),
                    ], indirect=True
                )
                def test_foo(dut):
                    pass
                """)
            )

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='esp32s2,esp32s3')
        assert len(test_related_apps) == 2
        assert len(non_test_related_apps) == 0

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='esp32,esp32s3,esp32')
        assert len(test_related_apps) == 2
        assert len(non_test_related_apps) == 0

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')
        assert len(test_related_apps) == 3
        assert len(non_test_related_apps) == len(SUPPORTED_TARGETS) - 3

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='foo,bar')
        assert len(test_related_apps) == 0
        assert len(non_test_related_apps) == 0

    def test_modified_pytest_script(self, tmp_path: Path) -> None:
        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

        (tmp_path / 'test_modified_pytest_script.py').write_text(
            textwrap.dedent("""
            import pytest
            import os

            @pytest.mark.parametrize('count, target', [(2, 'esp32')], indirect=True)
            @pytest.mark.parametrize('app_path', [
                    '{}|{}'.format(os.path.join(os.path.dirname(__file__), 'foo'),
                                   os.path.join(os.path.dirname(__file__), 'bar')),
                ], indirect=True
            )
            def test_multi_foo_bar(dut):
                pass
            """),
            encoding='utf-8',
        )

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')
        assert len(test_related_apps) == 2  # foo-esp32, bar-esp32
        assert len(non_test_related_apps) == 2 * len(SUPPORTED_TARGETS) - 2

        test_related_apps, non_test_related_apps = get_all_apps(
            paths=[str(tmp_path)], target='all', modified_files=[], modified_components=[]
        )
        assert len(test_related_apps) == 0
        assert len(non_test_related_apps) == 0

        test_related_apps, non_test_related_apps = get_all_apps(
            paths=[str(tmp_path)],
            target='all',
            modified_files=[str(tmp_path / 'test_modified_pytest_script.py')],
            modified_components=[],
        )
        assert len(test_related_apps) == 2
        assert len(non_test_related_apps) == 0

    def test_host_test_script(self, tmp_path: Path) -> None:
        create_project('foo', tmp_path)
        (tmp_path / 'foo' / 'sdkconfig.ci').touch()
        (tmp_path / 'foo' / 'sdkconfig.ci.linux').write_text('CONFIG_IDF_TARGET="linux"\n', encoding='utf-8')

        with open(tmp_path / 'foo' / 'test_host_test_script.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
                import pytest

                @pytest.mark.parametrize('target', [
                    'linux',
                ], indirect=True)
                def test_foo(dut):
                    pass

                @pytest.mark.parametrize('target', [
                    'esp32',
                ], indirect=True)
                @pytest.mark.qemu
                def test_foo_qemu(dut):
                    pass
                """)
            )

        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')

        assert len(test_related_apps) == 0
        assert len(non_test_related_apps) == len(SUPPORTED_TARGETS)

        # by default, linux is not built
        test_related_apps, non_test_related_apps = get_all_apps(
            paths=[str(tmp_path)], target='all', marker_expr='host_test'
        )
        assert len(test_related_apps) == 1
        assert len(non_test_related_apps) == len(SUPPORTED_TARGETS) - 1

        # specify linux
        test_related_apps, non_test_related_apps = get_all_apps(
            paths=[str(tmp_path)],
            target='linux',
        )
        assert len(test_related_apps) == 1
        assert len(non_test_related_apps) == 0

    def test_collected_apps_files_found(self, tmp_path: Path) -> None:
        # Create projects first
        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

        settings = CiSettings()

        # Create test-related apps file
        test_app = CMakeApp(  # type: ignore[call-arg]
            app_dir=os.path.join(str(tmp_path), 'foo'),
            target='esp32',
            config_name='default',
            build_system='cmake',
            build_status=BuildStatus.SUCCESS,
        )

        dump_apps_to_txt([test_app], settings.collected_test_related_apps_filepath)

        # Create non-test-related apps file
        non_test_app = CMakeApp(  # type: ignore[call-arg]
            app_dir=os.path.join(str(tmp_path), 'bar'),
            target='esp32s2',
            config_name='default',
            build_system='cmake',
            build_status=BuildStatus.SUCCESS,
        )

        dump_apps_to_txt([non_test_app], settings.collected_non_test_related_apps_filepath)

        # Test the get_all_apps function
        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')

        # Verify that the apps were read from the files
        assert len(test_related_apps) == 1
        assert len(non_test_related_apps) == 1

        # Verify the content of the apps
        assert test_related_apps[0].app_dir == os.path.join(str(tmp_path), 'foo')
        assert test_related_apps[0].target == 'esp32'
        assert test_related_apps[0].config_name == 'default'

        assert non_test_related_apps[0].app_dir == os.path.join(str(tmp_path), 'bar')
        assert non_test_related_apps[0].target == 'esp32s2'
        assert non_test_related_apps[0].config_name == 'default'

        # Test with specific target to ensure the cached apps are still used
        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='esp32')

        # Should still return both apps because the cached files override target-specific filtering
        assert len(test_related_apps) == 1
        assert len(non_test_related_apps) == 1

        # remove the test-related apps file and test again
        os.remove(settings.collected_test_related_apps_filepath)
        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')
        assert len(test_related_apps) == 0
        assert len(non_test_related_apps) == 1

        # remove all files and test again
        os.remove(settings.collected_non_test_related_apps_filepath)
        test_related_apps, non_test_related_apps = get_all_apps(paths=[str(tmp_path)], target='all')
        assert len(test_related_apps) == 0
        assert len(non_test_related_apps) == len(SUPPORTED_TARGETS) * 2
