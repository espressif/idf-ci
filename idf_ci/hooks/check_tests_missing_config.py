# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
import typing as t
import warnings
from collections import defaultdict
from pathlib import Path

from idf_ci.build_collect.scripts import collect_apps
from idf_ci.utils import parse_tuple_from_string

# Disable logs for clean output
logging.disable(logging.CRITICAL)

# Skip pydantic warnings from idf-build-apps
warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    message=r'Config key `pyproject_toml_.*` is set in model_config',
)


def parse_config_from_caseid(caseid: str) -> t.Union[str, tuple]:
    """Parse config from caseid.

    Examples:
        - 'esp32.release.test_foo' -> 'release'
        - "('esp32', 'esp32c3').('a', 'b').test_foo" -> ('a', 'b')
        - "('esp32', 'esp32').('a', 'a').test_foo" -> 'a'
    """
    _, config, _ = caseid.split('.', 2)

    try:
        # ('default', 'release') -> {'default', 'release'}
        # ('default', 'default') -> {'default'}
        parsed = set(parse_tuple_from_string(config))

        # If only one unique element, extract it
        return parsed.pop() if len(parsed) == 1 else tuple(sorted(parsed))
    except RuntimeError:
        return config


def filter_redundant_tuple_configs(
    config_test_case_map: t.Dict[t.Union[str, tuple], t.List[str]],
) -> t.Dict[t.Union[str, tuple], t.List[str]]:
    """Filter config map to remove redundant tuple configs."""

    # Configs that are strings are 100% missing
    missing_configs = {c for c in config_test_case_map if isinstance(c, str)}

    result: t.Dict[t.Union[str, tuple], t.List[str]] = {}
    for config, test_names in config_test_case_map.items():
        if isinstance(config, str):
            result[config] = test_names
        else:
            # Remove already-known missing configs from tuple
            filtered = tuple(c for c in config if c not in missing_configs)
            if not filtered:
                continue
            # If only one config remains, extract it
            filtered = filtered[0] if len(filtered) == 1 else filtered
            result[filtered] = test_names

    return result


def format_missing_config_error(config: t.Union[str, tuple], test_names: t.List[str]) -> str:
    """Format error message for missing config(s) and associated test cases."""
    if isinstance(config, str):
        msg = f'Sdkconfig file "{config}" is missing'
    else:
        config_str = '", "'.join(config)
        msg = f'Some of sdkconfig files ("{config_str}") are missing'

    if len(test_names) == 1:
        return f'\t{msg} for test case "{test_names[0]}"\n'

    lines = [f'\t{msg} for test cases:\n']
    for test_name in test_names:
        lines.append(f'\t\t- {test_name}\n')
    return ''.join(lines)


def main():
    filenames = sys.argv[1:]
    paths = set()
    has_errors = False

    # Get list of unique directories where files were changed
    for filename in filenames:
        path = Path(filename)
        path_dir = path.parent if path.is_file() else path

        # Ignore current directory
        if path_dir == Path('.'):
            continue

        paths.add(str(path_dir))

    data = collect_apps(sorted(paths))
    err_output = (
        'Error: Test cases requiring nonexistent sdkconfig files.\n\n'
        'Please make sure the following sdkconfig files exist or update config name in test case parameters.\n'
        'For more information, refer to documentation: https://docs.espressif.com/projects/idf-build-apps/en/latest/explanations/config_rules.html\n\n'
    )

    for project_name, project_data in data['projects'].items():
        test_cases_nonexistent_app = project_data.get('test_cases_requiring_nonexistent_app', [])

        # If there are test cases with nonexistent sdkconfig files, add them to the error output
        if len(test_cases_nonexistent_app) > 0:
            has_errors = True
            err_output += f'{project_name}\n'

            # Group test cases by config
            config_test_case_map = defaultdict(set)
            for caseid in test_cases_nonexistent_app:
                config = parse_config_from_caseid(caseid)
                _, _, test_name = caseid.split('.', 2)
                config_test_case_map[config].add(test_name)

            # Convert sets to sorted lists
            config_test_case_map = {k: sorted(v) for k, v in config_test_case_map.items()}

            # Filter redundant tuple configs and format output
            filtered_map = filter_redundant_tuple_configs(config_test_case_map)
            for config, test_names in filtered_map.items():
                err_output += format_missing_config_error(config, test_names)

            err_output += '\n'

    if has_errors:
        print(err_output.rstrip())
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
