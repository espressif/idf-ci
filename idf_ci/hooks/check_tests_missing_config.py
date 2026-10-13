# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import sys
import typing as t
import warnings
from collections import defaultdict
from pathlib import Path

import click
from idf_build_apps.app import App
from idf_build_apps.args import FindArguments
from idf_build_apps.finder import find_app_configs

from idf_ci.build_collect.scripts import collect_test_apps
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
    test_apps = collect_test_apps(paths=[str(d) for d in filtered_dirs] if filtered_dirs else None)
    missing: t.Dict[str, t.Dict[str, t.Set[str]]] = defaultdict(lambda: defaultdict(set))
    if test_apps:
        args = FindArguments(enable_preview_targets=True)
        configs_by_path_target: t.Dict[t.Tuple[str, str], t.Optional[t.Set[str]]] = {}
        for app_key, cases in test_apps.items():
            key = (app_key.path, app_key.target)
            if key not in configs_by_path_target:
                configs_by_path_target[key] = (
                    {
                        name
                        for _, name in find_app_configs(
                            app_key.path,
                            args.config_rules,
                            target=app_key.target,
                            sdkconfig_defaults=args.sdkconfig_defaults,
                        )
                    }
                    if t.cast(t.Type[App], args.build_system).is_app(app_key.path)
                    else None
                )
            configs = configs_by_path_target[key]
            if configs is None:
                continue

            if app_key.config not in configs:
                missing[app_key.path][app_key.config].update(case.name for case in cases)

    err_output = (
        'Error: Test cases requiring missing sdkconfig files.\n\n'
        'Please make sure the following sdkconfig files exist or update config name in test case parameters.\n'
        'For more information, refer to documentation: https://docs.espressif.com/projects/idf-build-apps/en/latest/explanations/config_rules.html\n\n'
    )
    for project_path, config_test_case_map in missing.items():
        has_errors = True
        err_output += f'{project_path}\n'

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
