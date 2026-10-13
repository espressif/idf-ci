# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import re
import sys
import typing as t
import warnings
from collections import defaultdict
from pathlib import Path

import click
from idf_build_apps.app import App
from idf_build_apps.args import FindArguments
from idf_build_apps.constants import ALL_TARGETS
from idf_build_apps.utils import config_rules_from_str

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


def available_configs(directory: Path, rules: t.Optional[t.List[str]]) -> t.Dict[str, t.List[t.Optional[Path]]]:
    """Resolve config names using idf-build-apps' file and default rules, without constructing Apps."""
    configs: t.Dict[str, t.List[t.Optional[Path]]] = defaultdict(list)
    parsed_rules = config_rules_from_str(rules)
    matched_file = False
    default_name = ''

    for rule in parsed_rules:
        if getattr(rule, 'negated', False):
            continue
        if not rule.file_name:
            default_name = rule.config_name
            continue

        paths = sorted(directory.glob(rule.file_name))
        matched_file |= bool(paths)
        for path in paths:
            if any(path.name.endswith(f'.{target}') for target in ALL_TARGETS):
                continue
            name = rule.config_name
            if '*' in rule.file_name:
                match = re.match(r'.*' + rule.file_name.replace('.', r'\.').replace('*', r'(.*)'), str(path))
                assert match is not None
                name = name or match.group(1)
            configs[name].append(path)

    excluded = {
        path.resolve()
        for rule in parsed_rules
        if getattr(rule, 'negated', False)
        for path in directory.glob(rule.file_name)
    }
    for name in list(configs):
        configs[name] = [path for path in configs[name] if path is not None and path.resolve() not in excluded]
        if not configs[name]:
            del configs[name]
    if not matched_file:
        configs[default_name].append(None)

    return configs


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
        configs_by_path: t.Dict[str, t.Optional[t.Dict[str, t.List[t.Optional[Path]]]]] = {}
        for app_key, cases in test_apps.items():
            if app_key.path not in configs_by_path:
                configs_by_path[app_key.path] = (
                    available_configs(Path(app_key.path), args.config_rules)
                    if t.cast(t.Type[App], args.build_system).is_app(app_key.path)
                    else None
                )
            configs = configs_by_path[app_key.path]
            if configs is None:
                continue

            for sdkconfig in configs.get(app_key.config, []):
                # idf-build-apps rejects a config that specifies a different target.
                defaults = args.sdkconfig_defaults or os.getenv('SDKCONFIG_DEFAULTS') or 'sdkconfig.defaults'
                candidates = [Path(app_key.path) / name for name in defaults.split(';')]
                if sdkconfig is not None:
                    candidates.append(sdkconfig)
                defined_target = None
                for candidate in candidates:
                    if candidate.is_file():
                        for line in candidate.read_text().splitlines():
                            match = re.match(r'^CONFIG_IDF_TARGET="?([^"\n]*)"?$', os.path.expandvars(line))
                            if match:
                                defined_target = match.group(1)
                if defined_target is None or defined_target == app_key.target:
                    break
            else:
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
