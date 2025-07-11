# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import textwrap
from pathlib import Path

import pytest
from conftest import create_project

from idf_ci.scripts import build


@pytest.mark.skipif(not os.getenv('IDF_PATH'), reason='IDF_PATH is not set')
class TestBuild:
    @pytest.fixture(autouse=True)
    def setup_test_projects(self, tmp_path: Path):
        """tmp_path/foo
            - test_foo.py
                  - test_foo_slow (-m slow)

        tmp_path/bar
            - test_bar.py
                  - test_bar_slow (-m slower)

        - filter_expr='slow' should match both test_foo_slow and test_bar_slow
        - marker_expr='slow' should match only test_foo_slow
        - marker_expr='slower' should match only test_bar_slow
        """

        create_project('foo', tmp_path)
        create_project('bar', tmp_path)

        with open(tmp_path / 'foo' / 'test_foo.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('target', [
                'esp32',
            ], indirect=True)
            @pytest.mark.slow
            def test_foo_slow(dut):
                pass
            """)
            )

        with open(tmp_path / 'bar' / 'test_bar.py', 'w') as fw:
            fw.write(
                textwrap.dedent("""
            import pytest

            @pytest.mark.parametrize('target', [
                'esp32',
            ], indirect=True)
            @pytest.mark.slower
            def test_bar_slow(dut):
                pass
            """)
            )

        self.paths = [str(tmp_path / 'foo'), str(tmp_path / 'bar')]
        self.tmp_path = tmp_path

    def test_build_with_filter_or_marker_sets_only_test_related(self) -> None:
        # Test: Build without filter_expr and without only_test_related
        built_apps, _ = build(
            paths=self.paths,
            dry_run=True,
        )
        assert len(built_apps) > 2

        # Test: Build with filter_expr
        built_apps, _ = build(
            paths=self.paths,
            filter_expr='slow',
            dry_run=True,
        )
        assert len(built_apps) == 2

        # Test: Build with marker_expr
        built_apps, _ = build(
            paths=self.paths,
            marker_expr='slow',
            dry_run=True,
        )
        assert len(built_apps) == 1

        built_apps, _ = build(
            paths=self.paths,
            marker_expr='slower',
            dry_run=True,
        )
        assert len(built_apps) == 1

        # Test: Build with filter_expr and explicitly set only_test_related=False
        built_apps, _ = build(
            paths=self.paths,
            filter_expr='slow',
            only_test_related=False,
            dry_run=True,
        )
        assert len(built_apps) == 2

        # Test: Build with marker_expr and explicitly set only_test_related=False
        built_apps, _ = build(
            paths=self.paths,
            marker_expr='slow',
            only_test_related=False,
            dry_run=True,
        )
        assert len(built_apps) == 1

        # Test: Build with only_test_related=True but no filter_expr
        built_apps, _ = build(
            paths=self.paths,
            only_test_related=True,
            dry_run=True,
        )
        assert len(built_apps) == 2

        # Test: Build with only_non_test_related=True
        # Should build only non-test-related apps
        built_apps, _ = build(
            paths=self.paths,
            target='esp32',
            only_non_test_related=True,
            dry_run=True,
        )

        # Should build only non-test-related apps (none for esp32 since foo and bar are test-related)
        assert len(built_apps) == 0
