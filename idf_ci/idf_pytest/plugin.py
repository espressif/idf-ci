# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import logging
import os
import re
import sys
import typing as t
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from _pytest.config import Config
from _pytest.fixtures import FixtureRequest
from _pytest.python import Function
from _pytest.stash import StashKey
from pytest_embedded.plugin import multi_dut_argument, multi_dut_fixture

from .models import PytestCase

_MODULE_NOT_FOUND_REGEX = re.compile(r"No module named '(.+?)'")
CASE_STASH_KEY = StashKey[t.Optional[PytestCase]]()

LOGGER = logging.getLogger(__name__)


def _try_import(path: Path):
    spec = importlib.util.spec_from_file_location('', path)
    # write these if to make mypy happy
    if spec:
        module = importlib.util.module_from_spec(spec)
        if spec.loader and module:
            spec.loader.exec_module(module)


class IdfPytestPlugin:
    def __init__(
        self,
        *,
        cli_target: str,
        sdkconfig_name: t.Optional[str] = None,
    ) -> None:
        """
        :param cli_target: target passed from command line, could be single target, comma separated targets, or 'all'
        :param sdkconfig_name: run only tests whose apps are built with this sdkconfig name
        """
        self.cli_target = cli_target
        self.sdkconfig_name = sdkconfig_name

        self._testing_items: t.Set[pytest.Item] = set()

    @property
    def cases(self) -> t.List[PytestCase]:
        return sorted([c for i in self._testing_items if (c := self.get_case_by_item(i))], key=lambda x: x.caseid)

    @staticmethod
    def get_case_by_item(item: pytest.Item) -> t.Optional[PytestCase]:
        return item.stash.get(CASE_STASH_KEY, None)

    @pytest.fixture
    @multi_dut_argument
    def target(self, request: FixtureRequest) -> str:
        _t = getattr(request, 'param', None) or request.config.getoption('target', None)
        if not _t:
            raise ValueError(
                '"target" shall either be defined in pytest.mark.parametrize or be passed in command line by --target'
            )
        return _t

    @pytest.fixture
    @multi_dut_argument
    def config(self, request: FixtureRequest) -> str:
        return getattr(request, 'param', None) or 'default'

    @pytest.fixture
    @multi_dut_fixture
    def build_dir(
        self,
        request: FixtureRequest,
        app_path: str,
        target: t.Optional[str],
        config: t.Optional[str],
    ) -> str:
        """
        Check local build dir with the following priority:

        1. build_<target>_<config>
        2. build_<target>
        3. build_<config>
        4. build

        Returns:
            valid build directory
        """
        check_dirs = []
        build_dir_arg = request.config.getoption('build_dir', None)
        if build_dir_arg:
            check_dirs.append(build_dir_arg)
        if target is not None and config is not None:
            check_dirs.append(f'build_{target}_{config}')
        if target is not None:
            check_dirs.append(f'build_{target}')
        if config is not None:
            check_dirs.append(f'build_{config}')
        check_dirs.append('build')

        for check_dir in check_dirs:
            binary_path = os.path.join(app_path, check_dir)
            if os.path.isdir(binary_path):
                logging.info(f'found valid binary path: {binary_path}')
                return check_dir

            logging.warning('checking binary path: %s... missing... try another place', binary_path)

        raise ValueError(
            f'no build dir valid. Please build the binary via "idf.py -B {check_dirs[0]} build" and run pytest again'
        )

    @pytest.hookimpl(tryfirst=True)
    def pytest_pycollect_makemodule(
        self,
        module_path: Path,
    ):
        # no need to install third-party packages for collecting
        # try to eliminate ModuleNotFoundError in test scripts
        while True:
            try:
                _try_import(module_path)
            except ModuleNotFoundError as e:
                if res := _MODULE_NOT_FOUND_REGEX.search(e.msg):
                    # redirect_stderr somehow breaks the sys.stderr.write() method
                    # fix it when implement proper logging
                    pkg = res.group(1)
                    logging.warning(f'WARNING:Mocking missed package while collecting: {pkg}\n')
                    sys.modules[pkg] = MagicMock()
                    continue
            else:
                break

    @pytest.hookimpl(wrapper=True)
    def pytest_collection_modifyitems(self, config: Config, items: t.List[Function]):
        # add markers definitions
        config.addinivalue_line('markers', 'host_test: this test case runs on host machines')

        for item in items:
            item.stash[CASE_STASH_KEY] = PytestCase.from_item(item, cli_target=self.cli_target)

        deselected_items: t.List[Function] = []

        # add markers to items
        for item in items:
            _c = self.get_case_by_item(item)
            if _c is None:
                continue

            if 'qemu' in _c.all_markers or 'linux' in _c.targets:
                item.add_marker(pytest.mark.host_test)

        yield

        # filter by target
        if self.cli_target != 'all':
            res = []
            for item in items:
                _c = self.get_case_by_item(item)
                if _c is None:
                    continue

                if _c.target_selector != self.cli_target:
                    item.add_marker(pytest.mark.skip(reason=f'target mismatch: {self.cli_target}'))
                    deselected_items.append(item)
                else:
                    res.append(item)
            items[:] = res

        # filter by sdkconfig_name
        if self.sdkconfig_name:
            res = []
            for item in items:
                _c = self.get_case_by_item(item)
                if _c is None:
                    continue

                if self.sdkconfig_name not in set(app.config for app in _c.apps):
                    item.add_marker(pytest.mark.skip(reason=f'sdkconfig name mismatch: {self.sdkconfig_name}'))
                    deselected_items.append(item)
                else:
                    res.append(item)
            items[:] = res

        # deselected items should be added to config.hook.pytest_deselected
        config.hook.pytest_deselected(items=deselected_items)

        # add them to self._testing_items
        self._testing_items.update(items)
