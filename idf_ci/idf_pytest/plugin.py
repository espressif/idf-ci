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

from ..settings import CiSettings
from ..utils import setup_logging
from .models import PytestCase

_MODULE_NOT_FOUND_REGEX = re.compile(r"No module named '(.+?)'")
IDF_CI_PYTEST_CASE_KEY = StashKey[t.Optional[PytestCase]]()
IDF_CI_PYTEST_DEBUG_INFO_KEY = StashKey[t.Dict[str, t.Any]]()
IDF_CI_PLUGIN_KEY = StashKey['IdfPytestPlugin']()

logger = logging.getLogger(__name__)


##########
# Plugin #
##########
class IdfPytestPlugin:
    def __init__(
        self,
        *,
        cli_target: str,
        sdkconfig_name: t.Optional[str] = None,
    ) -> None:
        """Initialize the IDF pytest plugin.

        :param cli_target: Target passed from command line - single target, comma
            separated targets, or 'all'
        :param sdkconfig_name: Filter tests whose apps are built with this sdkconfig
            name
        """
        self.cli_target = cli_target
        self.sdkconfig_name = sdkconfig_name
        self.apps = CiSettings().get_built_apps_list()

        self.cases: t.List[PytestCase] = []

    @staticmethod
    def get_case_by_item(item: pytest.Item) -> t.Optional[PytestCase]:
        """Get the test case associated with a pytest item.

        :param item: The pytest test item

        :returns: PytestCase object or None if not found
        """
        return item.stash.get(IDF_CI_PYTEST_CASE_KEY, None)

    @pytest.fixture
    @multi_dut_argument
    def target(
        self,
        request: FixtureRequest,
    ) -> str:
        """Fixture that provides the target for tests.

        :param request: Pytest fixture request

        :returns: Target string

        :raises ValueError: If target parameter is not defined
        """
        target_value = getattr(request, 'param', None)
        if not target_value:
            raise ValueError('"target" must be defined in pytest.mark.parametrize')
        return target_value

    @pytest.fixture
    @multi_dut_argument
    def config(self, request: FixtureRequest) -> str:
        """Fixture that provides the configuration for tests.

        :param request: Pytest fixture request

        :returns: Configuration string, defaults to 'default' if not specified
        """
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
        """Find a valid build directory based on priority rules.

        Checks local build directories in the following order:

        1. build_<target>_<config>
        2. build_<target>
        3. build_<config>
        4. build

        :param request: Pytest fixture request
        :param app_path: Path to the application
        :param target: Target being used
        :param config: Configuration being used

        :returns: Valid build directory name

        :raises ValueError: If no valid build directory is found
        """
        check_dirs = []
        build_dir_arg = request.config.getoption('build_dir')

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
                logger.info(f'Found valid binary path: {binary_path}')
                return check_dir

            logger.warning('Checking binary path: %s... missing... trying another location', binary_path)

        raise ValueError(
            'No valid build directory found. '
            f'Please build the binary via "idf.py -B {check_dirs[0]} build" and run pytest again'
        )

    @pytest.hookimpl(tryfirst=True)
    def pytest_pycollect_makemodule(
        self,
        module_path: Path,
    ):
        """Handle module collection for pytest, mocking any missing modules.

        This hook runs before module collection to prevent errors from missing
        dependencies by automatically mocking them.

        :param module_path: Path to the module being collected
        """
        while True:
            try:
                spec = importlib.util.spec_from_file_location('', module_path)
                if spec:
                    module = importlib.util.module_from_spec(spec)
                    if spec.loader and module:
                        spec.loader.exec_module(module)
                break
            except ModuleNotFoundError as e:
                match = _MODULE_NOT_FOUND_REGEX.search(e.msg)
                if match:
                    pkg = match.group(1)
                    logger.warning('Mocking missing package during collection: %s', pkg)
                    sys.modules[pkg] = MagicMock()
                    continue

    @pytest.hookimpl(wrapper=True)
    def pytest_collection_modifyitems(self, config: Config, items: t.List[Function]):
        """Filter test cases based on target, sdkconfig, and available apps.

        :param config: Pytest configuration
        :param items: Collected test items
        """
        # Create PytestCase objects for all items
        for item in items:
            item.stash[IDF_CI_PYTEST_CASE_KEY] = PytestCase.from_item(item)
            item.stash[IDF_CI_PYTEST_DEBUG_INFO_KEY] = dict()

        # Add markers to items
        for item in items:
            case = self.get_case_by_item(item)
            if case is None:
                continue

            # Add 'host_test' marker to host test cases
            if 'qemu' in case.all_markers or 'linux' in case.targets:
                item.add_marker(pytest.mark.host_test)

        yield

        deselected_items: t.List[Function] = []

        # Filter by nightly_run marker
        if os.getenv('INCLUDE_NIGHTLY_RUN') == '1':
            # Include both nightly_run and non-nightly_run cases
            pass
        else:  # Determine if we should select nightly_run tests or non-nightly_run tests
            nightly_or_not = os.getenv('NIGHTLY_RUN') == '1'
            filtered_items = []
            for item in items:
                case = self.get_case_by_item(item)
                if case is None:
                    continue

                if ('nightly_run' in case.all_markers) == nightly_or_not:
                    filtered_items.append(item)
                else:
                    deselected_items.append(item)
            items[:] = filtered_items

        # Filter by target
        if self.cli_target != 'all':
            filtered_items = []
            for item in items:
                case = self.get_case_by_item(item)
                if case is None:
                    continue

                if case.target_selector != self.cli_target:
                    item.add_marker(pytest.mark.skip(reason=f'Target mismatch: {self.cli_target}'))
                    deselected_items.append(item)
                else:
                    filtered_items.append(item)
            items[:] = filtered_items

        # Filter by sdkconfig_name
        if self.sdkconfig_name:
            filtered_items = []
            for item in items:
                case = self.get_case_by_item(item)
                if case is None:
                    continue

                if self.sdkconfig_name not in set(app.config for app in case.apps):
                    item.stash[IDF_CI_PYTEST_DEBUG_INFO_KEY]['skip_reason'] = (
                        f'sdkconfig name mismatch. '
                        f'app sdkconfigs: {case.configs}, but CLI specified: {self.sdkconfig_name}'
                    )
                    deselected_items.append(item)
                else:
                    filtered_items.append(item)
            items[:] = filtered_items

        # Filter by app list
        if self.apps is not None:
            app_dirs = [os.path.abspath(app.build_path) for app in self.apps]
            filtered_items = []
            for item in items:
                case = self.get_case_by_item(item)
                if case is None:
                    continue

                skip_reason = case.get_skip_reason_if_not_built(app_dirs)
                if skip_reason:
                    item.stash[IDF_CI_PYTEST_DEBUG_INFO_KEY]['skip_reason'] = skip_reason
                    deselected_items.append(item)
                else:
                    filtered_items.append(item)
            items[:] = filtered_items

        # Report deselected items
        config.hook.pytest_deselected(items=deselected_items)

    def pytest_report_collectionfinish(self, items: t.List[Function]) -> None:
        for item in items:
            case = self.get_case_by_item(item)
            if case is None:
                continue

            self.cases.append(case)


##################
# Hook Functions #
##################
def pytest_addoption(parser: pytest.Parser):
    """Add custom command line options for IDF pytest plugin.

    :param parser: Pytest command line parser
    """
    # CLI values
    idf_ci_group = parser.getgroup('idf_ci')
    idf_ci_group.addoption(
        '--sdkconfig',
        help='Run only tests whose apps are built with this sdkconfig name',
    )

    # INI values
    parser.addini(
        'env_markers',
        help='Markers that indicate the running environment of the test case. '
        'Each line is a `<marker_name>: <marker_description>` pair',
        type='linelist',
    )


def pytest_configure(config: Config):
    """Configure the pytest environment for IDF tests.

    :param config: Pytest configuration object
    """
    setup_logging(config.getoption('log_cli_level'))

    cli_target = config.getoption('target') or 'all'
    sdkconfig_name = config.getoption('sdkconfig')

    env_markers: t.Set[str] = set()
    for line in config.getini('env_markers'):
        name, _ = line.split(':', maxsplit=1)
        config.addinivalue_line('markers', line)
        env_markers.add(name)

    PytestCase.KNOWN_ENV_MARKERS = env_markers

    plugin = IdfPytestPlugin(cli_target=cli_target, sdkconfig_name=sdkconfig_name)
    config.stash[IDF_CI_PLUGIN_KEY] = plugin
    config.pluginmanager.register(plugin)

    # Add markers definitions
    config.addinivalue_line('markers', 'host_test: this test case runs on host machines')
    config.addinivalue_line('markers', 'nightly_run: this test case is a nightly run')


def pytest_unconfigure(config: Config):
    """Clean up the IDF pytest plugin when pytest is shutting down.

    :param config: Pytest configuration object
    """
    plugin = config.stash.get(IDF_CI_PLUGIN_KEY, None)
    if plugin:
        del config.stash[IDF_CI_PLUGIN_KEY]
        config.pluginmanager.unregister(plugin)
