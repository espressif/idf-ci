# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
import typing as t
import warnings
from collections import defaultdict
from pathlib import Path

import click

from idf_ci.build_collect.models import CollectResult
from idf_ci.build_collect.scripts import collect_apps
from idf_ci.utils import remove_subfolders

# Disable logs for clean output
logging.disable(logging.CRITICAL)

# Skip pydantic warnings from idf-build-apps
warnings.filterwarnings(
    'ignore',
    category=UserWarning,
    message=r'Config key `pyproject_toml_.*` is set in model_config',
)


@click.command()
@click.argument('paths', nargs=-1, type=click.Path(exists=True))
def main(paths: t.Tuple[str, ...]):
    """Checks if any test cases require sdkconfig files that are missing."""

    dirs = set()
    has_errors = False

    # Get list of unique directories where files were changed
    for path in paths:
        p = Path(path)
        path_dir = p.parent if p.is_file() else p
        dirs.add(str(path_dir))

    filtered_dirs = remove_subfolders(list(dirs))

    data: CollectResult = collect_apps(paths=[str(d) for d in filtered_dirs] if filtered_dirs else None)
    err_output = (
        'Error: Test cases requiring missing sdkconfig files.\n\n'
        'Please make sure the following sdkconfig files exist or update config name in test case parameters.\n'
        'For more information, refer to documentation: https://docs.espressif.com/projects/idf-build-apps/en/latest/explanations/config_rules.html\n\n'
    )

    for project_path, project_data in data.projects.items():
        missing_apps = project_data.missing_apps

        if not missing_apps:
            continue

        # Group test cases by config
        config_test_case_map = defaultdict(set)
        for app in missing_apps:
            for test_case in app.test_cases:
                config_test_case_map[app.config].add(test_case.name)

        if not config_test_case_map:
            continue

        has_errors = True
        err_output += f'{project_path}\n'

        # Format output
        for config, test_names in config_test_case_map.items():
            msg = f'Sdkconfig file "{config}" is missing'

            if len(test_names) == 1:
                err_output += f'\t{msg} for test case "{next(iter(test_names))}"\n'
                continue

            lines = [f'\t{msg} for test cases:\n']
            for test_name in test_names:
                lines.append(f'\t\t- {test_name}\n')

            err_output += ''.join(lines)

        err_output += '\n'

    if has_errors:
        click.echo(err_output.rstrip())
        sys.exit(1)


if __name__ == '__main__':
    main()
