# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import os
import typing as t
from collections import defaultdict
from functools import lru_cache
from typing import NamedTuple

from _pytest.python import Function
from pytest_embedded.plugin import parse_multi_dut_args
from pytest_embedded.utils import targets_to_marker

from idf_ci.utils import to_list

logger = logging.getLogger(__name__)


class PytestApp:
    """Represents a pytest app."""

    def __init__(self, path: str, target: str, config: str) -> None:
        self.path = os.path.abspath(path)
        self.target = target
        self.config = config or 'default'

    def __hash__(self) -> int:
        return hash((self.path, self.target, self.config))

    @property
    def build_dir(self) -> str:
        """Returns the build directory for the app.

        .. note::

            Matches the build_dir (by default build_@t_@w) in the idf-build-apps config
            file.

        :returns: The build directory for the app.
        """
        return os.path.join(self.path, f'build_{self.target}_{self.config}')


class PytestCase:
    """Represents a pytest test case."""

    KNOWN_ENV_MARKERS: t.ClassVar[t.Set[str]] = set()

    def __init__(self, apps: t.List[PytestApp], item: Function) -> None:
        self.apps = apps
        self.item = item

    @classmethod
    def get_param(cls, item: Function, key: str, default: t.Any = None) -> t.Any:
        """Get parameter value from pytest item.

        :param item: Pytest function item
        :param key: Parameter key to retrieve
        :param default: Default value if key not found

        :returns: Parameter value or default
        """
        # funcargs is not calculated while collection
        # callspec is something defined in parametrize
        if not hasattr(item, 'callspec'):
            return default

        return item.callspec.params.get(key, default) or default

    @classmethod
    def from_item(cls, item: Function) -> t.Optional['PytestCase']:
        """Create a PytestCase from a pytest item.

        :param item: Pytest function item

        :returns: PytestCase instance or None if targets not defined
        """
        count = cls.get_param(item, 'count', 1)

        # default app_path is where the test script locates
        app_paths = to_list(parse_multi_dut_args(count, cls.get_param(item, 'app_path', os.path.dirname(item.path))))
        configs = to_list(parse_multi_dut_args(count, cls.get_param(item, 'config', 'default')))
        targets = to_list(parse_multi_dut_args(count, cls.get_param(item, 'target', None)))  # defined fixture

        if targets is None or targets == [None] * count:
            logger.critical(
                'No "target" defined in `@pytest.mark.parametrize` for test function "%s" in file "%s. Skipping...',
                item.name,
                item.path,
            )
            return None

        return PytestCase(
            apps=[PytestApp(app_paths[i], targets[i], configs[i]) for i in range(count)],
            item=item,
        )

    def __hash__(self) -> int:
        return hash((self.path, self.name, self.apps, self.all_markers))

    @property
    def path(self) -> str:
        return str(self.item.path)

    @property
    def name(self) -> str:
        return self.item.originalname

    @property
    def targets(self) -> t.List[str]:
        # sequence matters
        return [app.target for app in self.apps]

    @property
    def target_selector(self) -> str:
        return ','.join(self.targets)

    @property
    def env_markers(self) -> t.Set[str]:
        return {marker for marker in self.all_markers if marker in self.KNOWN_ENV_MARKERS}

    @property
    def env_selector(self) -> str:
        # sequence not matters, sorted for consistency
        return ' and '.join(sorted(self.env_markers))  # pytest marker use 'and' to combine multiple markers

    @property
    def runner_tags(self) -> t.Tuple[str, ...]:
        return tuple(
            [
                targets_to_marker(self.targets),
                *self.env_markers,
            ]
        )

    @property
    def configs(self) -> t.List[str]:
        return [app.config for app in self.apps]

    @property
    def caseid(self) -> str:
        target_str = self.targets[0] if self.is_single_dut else str(tuple(self.targets))
        if 'qemu' in self.all_markers:
            target_str += '_qemu'
        configs = self.configs[0] if self.is_single_dut else tuple(self.configs)
        return f'{target_str}.{configs}.{self.name}'

    @property
    def is_single_dut(self) -> bool:
        return len(self.apps) == 1

    @property
    def is_host_test(self) -> bool:
        return 'host_test' in self.all_markers or 'linux' in self.targets

    @property
    def is_in_ci(self) -> bool:
        return 'CI_JOB_ID' in os.environ or 'GITHUB_ACTIONS' in os.environ

    @property
    def all_markers(self) -> t.Set[str]:
        return {marker.name for marker in self.item.iter_markers()}

    def get_skip_reason_if_not_built(self, app_dirs: t.Optional[t.List[str]] = None) -> t.Optional[str]:
        """Check if all binaries of the test case are built in the app lists.

        :param app_dirs: App folder paths to check

        :returns: Skip reason string if not all binaries are built, None otherwise
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

        msg += '\nMight be an issue with .build-test-rules.yml files'
        return msg


class GroupKey(NamedTuple):
    target_selector: str
    env_selector: str
    runner_tags: t.Tuple[str, ...]

    @classmethod
    def from_case(cls, case: PytestCase):
        return cls(case.target_selector, case.env_selector, case.runner_tags)


class GroupedPytestCases:
    """Groups pytest cases by target and environment markers."""

    def __init__(
        self, cases: t.List[PytestCase], *, additional_dict: t.Optional[t.Dict[GroupKey, t.Dict[str, t.Any]]] = None
    ) -> None:
        self.cases = cases

        self.additional_dict: t.Dict[GroupKey, t.Dict[str, t.Any]] = additional_dict or dict()

    @property
    @lru_cache()
    def grouped_cases(self) -> t.Dict[GroupKey, t.List[PytestCase]]:
        """Groups test cases by target and environment markers.

        :returns: Dictionary of GroupKey to list of PytestCases
        """
        grouped: t.Dict[GroupKey, t.List[PytestCase]] = defaultdict(list)
        for case in self.cases:
            grouped[GroupKey.from_case(case)].append(case)
        return grouped

    def output_as_string(self) -> str:
        """Generates a human-readable string representation of grouped test cases.

        :returns: String representation of grouped test cases
        """
        lines: t.List[str] = []
        for key, cases in self.grouped_cases.items():
            if not key.env_selector:
                lines.append(f'{key.target_selector}: {len(cases)} cases')
            else:
                lines.append(f'{key.target_selector} - {key.env_selector}: {len(cases)} cases')

            for c in cases:
                lines.append(f'\t{c.caseid}')

        return '\n'.join(lines)

    def output_as_github_ci(self) -> str:
        """Generates a JSON string for GitHub Actions CI matrix strategy.

        Example output:

        .. code-block:: json

            {
                "include": [
                    {
                        "targets": "esp32,esp32",
                        "env_markers": "generic and flash_4mb",
                        "runner_tags": ["self_hosted", "esp32_2", "generic", "flash_4mb"],
                        "nodes": "nodeid1 nodeid2"
                    },
                    {
                        "targets": "esp32,esp32s2",
                        "env_markers": "generic and two_duts",
                        "runner_tags": ["self_hosted", "esp32+esp32s2", "generic", "two_duts"],
                        "nodes": "nodeid1 nodeid2"
                    },
                    {
                        "targets": "esp32",
                        "env_markers": "generic",
                        "runner_tags": ["self_hosted", "esp32", "generic"],
                        "nodes": "nodeid1"
                    }
                ]
            }

        Example usage:

        .. code-block:: yaml

            strategy:
                matrix: ${{fromJson( this_output_as_env_var )}}

        :returns: JSON string suitable for GitHub Actions matrix strategy
        """
        include_list = []
        for key, cases in self.grouped_cases.items():
            include_list.append(
                {
                    'targets': key.target_selector,
                    'env_markers': key.env_selector,
                    'runner_tags': ['self-hosted', *key.runner_tags],  # self-hosted is required in github
                    'nodes': ' '.join([c.item.nodeid for c in cases]),
                }
            )

        return json.dumps({'include': include_list})
