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
from _pytest.fixtures import FixtureRequest
from pytest_embedded.plugin import multi_dut_argument, multi_dut_fixture

from .models import PytestCase

_MODULE_NOT_FOUND_REGEX = re.compile(r"No module named '(.+?)'")


def _try_import(path: Path):
    spec = importlib.util.spec_from_file_location('', path)
    # write these if to make mypy happy
    if spec:
        module = importlib.util.module_from_spec(spec)
        if spec.loader and module:
            spec.loader.exec_module(module)


class IdfPytestPlugin:
    def __init__(self, *, cli_target: str) -> None:
        self.cli_target = cli_target

        self._all_items_to_cases_d: t.Dict[pytest.Item, PytestCase] = {}
        self._testing_items: t.Set[pytest.Item] = set()

    @property
    def cases(self) -> t.List[PytestCase]:
        return [c for i, c in self._all_items_to_cases_d.items() if i in self._testing_items]

    @pytest.fixture
    @multi_dut_argument
    def target(self, request: FixtureRequest) -> str:
        _t = getattr(request, 'param', None) or request.config.getoption('target', None)
        if not _t:
            raise ValueError(
                '"target" shall either be defined in pytest.mark.parametrize '
                'or be passed in command line by --target'
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
                    if sys.__stderr__:
                        sys.__stderr__.write(f'WARNING:Mocking missed package while collecting: {pkg}\n')
                    sys.modules[pkg] = MagicMock()
                    continue
            else:
                break

    def pytest_collection_modifyitems(self, items):
        for item in items:
            if case := PytestCase.from_item(item, cli_target=self.cli_target):
                self._all_items_to_cases_d[item] = case

        # filter by target
        if self.cli_target != 'all':
            res = []
            for item, case in self._all_items_to_cases_d.items():
                if case.target_selector == self.cli_target:
                    res.append(item)
            items[:] = res

        # add them to self._testing_items
        for item in items:
            self._testing_items.add(item)
