# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import typing as t
from functools import cached_property

from _pytest.python import Function
from pytest_embedded.plugin import parse_multi_dut_args

from idf_ci.utils import to_list

LOGGER = logging.getLogger(__name__)


class PytestApp:
    """
    Represents a pytest app.
    """

    def __init__(self, path: str, target: str, config: str) -> None:
        self.path = os.path.abspath(path)
        self.target = target
        self.config = config or 'default'

    def __hash__(self) -> int:
        return hash((self.path, self.target, self.config))

    @property
    def build_dir(self) -> str:
        """
        Returns the build directory for the app.

        .. note::

            Matches the build_dir (by default build_@t_@w) in the build profile.

        :return: The build directory for the app.
        """
        return os.path.join(self.path, f'build_{self.target}_{self.config}')


class PytestCase:
    """
    Represents a pytest test case.
    """

    def __init__(self, apps: t.List[PytestApp], item: Function) -> None:
        self.apps = apps
        self.item = item

    @classmethod
    def get_param(cls, item: Function, key: str, default: t.Any = None) -> t.Any:
        # funcargs is not calculated while collection
        # callspec is something defined in parametrize
        if not hasattr(item, 'callspec'):
            return default

        return item.callspec.params.get(key, default) or default

    @classmethod
    def from_item(cls, item: Function, *, cli_target: str) -> t.Optional['PytestCase']:
        """
        Turn pytest item to PytestCase
        """
        count = cls.get_param(item, 'count', 1)

        # default app_path is where the test script locates
        app_paths = to_list(parse_multi_dut_args(count, cls.get_param(item, 'app_path', os.path.dirname(item.path))))
        configs = to_list(parse_multi_dut_args(count, cls.get_param(item, 'config', 'default')))
        targets = to_list(parse_multi_dut_args(count, cls.get_param(item, 'target')))  # defined fixture

        cli_targets = cli_target.split(',')
        if count > 1 and targets == [None] * count:
            targets = cli_targets
        elif targets is None:
            if count == len(cli_targets):
                LOGGER.debug('No param "target" for test case "%s", use CLI target "%s"', item.name, cli_target)
                targets = cli_targets
            else:
                LOGGER.warning(
                    'No param "target" for test case "%s". '
                    'current DUT count is %d, while CLI target count is %d. Skipping the test.',
                    item.name,
                    count,
                    len(cli_targets),
                )
                return None

        return PytestCase(
            apps=[PytestApp(app_paths[i], targets[i], configs[i]) for i in range(count)],
            item=item,
        )

    def __hash__(self) -> int:
        return hash((self.path, self.name, self.apps, self.all_markers))

    @cached_property
    def path(self) -> str:
        return str(self.item.path)

    @cached_property
    def name(self) -> str:
        return self.item.originalname

    @cached_property
    def targets(self) -> t.List[str]:
        return [app.target for app in self.apps]

    @cached_property
    def configs(self) -> t.List[str]:
        return [app.config for app in self.apps]

    @cached_property
    def caseid(self) -> str:
        if self.is_single_dut:
            return f'{self.targets[0]}.{self.configs[0]}.{self.name}'
        else:
            return f'{tuple(self.targets)}.{tuple(self.configs)}.{self.name}'

    @cached_property
    def is_single_dut(self) -> bool:
        return True if len(self.apps) == 1 else False

    @cached_property
    def is_host_test(self) -> bool:
        return 'host_test' in self.all_markers or 'linux' in self.targets

    @cached_property
    def is_in_ci(self) -> bool:
        return 'CI_JOB_ID' in os.environ or 'GITHUB_ACTIONS' in os.environ

    @cached_property
    def target_selector(self) -> str:
        return ','.join(app.target for app in self.apps)

    # the following markers could be changed dynamically, don't use cached_property
    @property
    def all_markers(self) -> t.Set[str]:
        return {marker.name for marker in self.item.iter_markers()}

    def get_skip_reason_if_not_built(self, app_dirs: t.Optional[t.List[str]] = None) -> t.Optional[str]:
        """
        Check if all binaries of the test case are built in the app lists.

        :param app_dirs: app folder paths to check
        :return: debug string if not all binaries are built in the app lists, None otherwise
        """
        if app_dirs is None:
            # ignore this feature
            return None

        bin_found = [0] * len(self.apps)
        for i, app in enumerate(self.apps):
            if app.build_dir in app_dirs:
                bin_found[i] = 1

        if sum(bin_found) == 0:
            msg = f'Skip test case {self.name} because all following binaries are not listed in the app lists: '
            for app in self.apps:
                msg += f'\n - {app.build_dir}'

            return msg

        if sum(bin_found) == len(self.apps):
            return None

        # some found, some not, looks suspicious
        msg = f'Found some binaries of test case {self.name} are not listed in the app lists.'
        for i, app in enumerate(self.apps):
            if bin_found[i] == 0:
                msg += f'\n - {app.build_dir}'

        msg += '\nMight be a issue of .build-test-rules.yml files'
        return msg
