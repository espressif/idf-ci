# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
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
from _pytest.python import Metafunc
from pytest_embedded.plugin import multi_dut_argument, multi_dut_fixture

from ..settings import get_ci_settings
from ..utils import setup_logging
from .models import PytestCase

_MODULE_NOT_FOUND_REGEX = re.compile(r"No module named '(.+?)'")
IDF_CI_PYTEST_CASE_KEY = pytest.StashKey[t.Optional[PytestCase]]()
IDF_CI_PYTEST_DEBUG_INFO_KEY = pytest.StashKey[t.Dict[str, t.Any]]()
IDF_CI_PLUGIN_KEY = pytest.StashKey['IdfPytestPlugin']()

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

        settings = get_ci_settings()
        if settings.is_in_ci:
            self.apps = settings.get_built_apps_list()
        else:
            self.apps = None

        self.cases: t.List[PytestCase] = []

    @staticmethod
    def get_case_by_item(item: pytest.Item) -> t.Optional[PytestCase]:
        """Get the test case associated with a pytest item.

        :param item: The pytest test item

        :returns: PytestCase object or None if not found
        """
        return item.stash.get(IDF_CI_PYTEST_CASE_KEY, None)

    @staticmethod
    def _format_case_id(
        target: t.Optional[t.Any],
        config: t.Optional[t.Any],
        case_name: str,
        *,
        is_qemu: bool = False,
        params: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> str:
        parts: t.List[str] = []
        if target:
            parts.append((str(target) + '_qemu') if is_qemu else str(target))
        if config:
            parts.append(str(config))
        parts.append(case_name)
        if params:
            parts.append(str(params))

        return '.'.join(parts)

    @staticmethod
    def _filtered_non_fixture_params(item: pytest.Function) -> t.Dict[str, t.Any]:
        if not hasattr(item, 'callspec'):
            return {}

        fixture_manager = item.session._fixturemanager
        return {k: v for k, v in item.callspec.params.items() if k not in fixture_manager._arg2fixturedefs}

    @staticmethod
    def _get_runtime_target_and_config(item: pytest.Function) -> t.Tuple[t.Any, t.Any]:
        target = item.funcargs.get('target')
        config = item.funcargs.get('config')
        if target is not None and config is not None:
            return target, config

        if hasattr(item, 'callspec'):
            return (
                item.callspec.params.get('target', target),
                item.callspec.params.get('config', config or 'default'),
            )

        return target, config or 'default'

    @classmethod
    def _custom_test_case_name(cls, item: pytest.Function) -> str:
        target, config = cls._get_runtime_target_and_config(item)
        is_qemu = item.get_closest_marker('qemu') is not None
        return cls._format_case_id(
            target,
            config,
            item.originalname,
            is_qemu=is_qemu,
            params=cls._filtered_non_fixture_params(item),
        )

    @staticmethod
    def _has_parametrized_arg(metafunc: Metafunc, arg_name: str) -> bool:
        for marker in metafunc.definition.iter_markers(name='parametrize'):
            if not marker.args:
                continue

            argnames = marker.args[0]
            if isinstance(argnames, str):
                names = [name.strip() for name in argnames.split(',')]
            else:
                names = list(argnames)

            if arg_name in names:
                return True

        # Other plugins may have already parametrized the argument via
        # pytest_generate_tests, which updates metafunc._calls but does not add
        # a parametrize marker to the definition.
        for callspec in getattr(metafunc, '_calls', []):
            if arg_name in callspec.params:
                return True

        return False

    @staticmethod
    def _is_linux_target_run(config: Config) -> bool:
        target = config.getoption('target')
        if not target:
            return False

        if isinstance(target, str):
            targets = [_t.strip() for _t in target.split(',')]
        else:
            targets = [str(_t).strip() for _t in target]

        return 'linux' in targets

    @pytest.fixture
    @multi_dut_argument
    def target(
        self,
        request: pytest.FixtureRequest,
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
    def config(self, request: pytest.FixtureRequest) -> str:
        """Fixture that provides the configuration for tests.

        :param request: Pytest fixture request

        :returns: Configuration string, defaults to 'default' if not specified
        """
        return getattr(request, 'param', None) or 'default'

    @pytest.fixture
    def test_case_name(self, request: pytest.FixtureRequest, target: t.Any, config: t.Any) -> str:
        item = request.node
        if not isinstance(item, pytest.Function):
            return request.node.nodeid

        is_qemu = item.get_closest_marker('qemu') is not None
        return self._format_case_id(
            target,
            config,
            item.originalname,
            is_qemu=is_qemu,
            params=self._filtered_non_fixture_params(item),
        )

    @pytest.fixture
    @multi_dut_fixture
    def build_dir(
        self,
        request: pytest.FixtureRequest,
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

    @pytest.hookimpl(trylast=True)
    def pytest_generate_tests(self, metafunc: Metafunc) -> None:
        if 'embedded_services' not in metafunc.fixturenames:
            return

        if self._has_parametrized_arg(metafunc, 'embedded_services'):
            return

        if metafunc.definition.get_closest_marker('qemu') is not None:
            metafunc.parametrize('embedded_services', ['idf,qemu'], indirect=True)
            return

        if self._is_linux_target_run(metafunc.config):
            metafunc.parametrize('embedded_services', ['idf'], indirect=True)

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
                if not match:
                    raise

                pkg = match.group(1)
                logger.warning('Mocking missing package during collection: %s', pkg)
                sys.modules[pkg] = MagicMock()
                continue

    @pytest.hookimpl(wrapper=True)
    def pytest_collection_modifyitems(self, config: pytest.Config, items: t.List[pytest.Function]):
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

        deselected_items: t.List[pytest.Function] = []

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

    def pytest_report_collectionfinish(self, items: t.List[pytest.Function]) -> None:
        for item in items:
            case = self.get_case_by_item(item)
            if case is None:
                continue

            self.cases.append(case)

    @pytest.hookimpl(hookwrapper=True, trylast=True)
    def pytest_runtest_makereport(self, item: pytest.Function):
        outcome = yield
        report = outcome.get_result()

        # should be called after pytest_custom_test_case_name is called to
        # ensure custom_test_case_name is set in the report
        custom_test_case_name = getattr(report, 'custom_test_case_name', None) or self._custom_test_case_name(item)

        # pytest-junitxml derives testcase names from nodeid. Preserve our
        # custom case name by overriding the xml reporter's name attribute.
        try:
            from _pytest.junitxml import xml_key
        except ImportError:
            return

        xml = item.config.stash.get(xml_key, None)
        if xml is not None:
            xml.node_reporter(item.nodeid).add_attribute('name', custom_test_case_name)

    @pytest.hookimpl(optionalhook=True)  # pytest-ignore-test-results
    def pytest_custom_test_case_name(self, item: pytest.Function) -> str:
        """Provide stable custom test case name for ignore-results matching."""
        return self._custom_test_case_name(item)


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


def pytest_configure(config: pytest.Config):
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


def pytest_unconfigure(config: pytest.Config):
    """Clean up the IDF pytest plugin when pytest is shutting down.

    :param config: Pytest configuration object
    """
    plugin = config.stash.get(IDF_CI_PLUGIN_KEY, None)
    if plugin:
        del config.stash[IDF_CI_PLUGIN_KEY]
        config.pluginmanager.unregister(plugin)
