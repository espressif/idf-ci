# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import time
import typing as t
from pathlib import Path

import click
from idf_build_apps import find_apps
from idf_build_apps.app import App
from idf_build_apps.args import FindArguments

from idf_ci import get_pytest_cases
from idf_ci.idf_pytest import PytestCase
from idf_ci.scripts import build as build_cmd

from .._compat import UNDEF
from ._options import (
    create_config_file,
    option_modified_files,
    option_output,
    option_parallel,
    option_paths,
    option_pytest,
    option_target,
)

logger = logging.getLogger(__name__)


@click.group()
def build():
    """Group of build related commands"""
    pass


@build.command()
@option_paths
@option_target
@option_parallel
@option_pytest
@option_modified_files
@click.option('--only-test-related', is_flag=True, default=None, help='Run build only for test-related apps')
@click.option('--only-non-test-related', is_flag=True, default=None, help='Run build only for non-test-related apps')
@click.option('--dry-run', is_flag=True, help='Run build in dry-run mode')
@click.option(
    '--build-system',
    default=UNDEF,
    help='Filter the apps by build system. Can be "cmake", "make" or a custom App class path in format "module:class"',
)
@click.pass_context
def run(
    ctx,
    *,
    paths,
    target,
    parallel_count,
    parallel_index,
    modified_files,
    only_test_related,
    only_non_test_related,
    dry_run,
    build_system,
    marker_expr,
    filter_expr,
):
    """Execute the build process for applications"""
    start_time = time.time()
    apps, ret = build_cmd(
        paths=paths,
        target=target,
        parallel_count=parallel_count,
        parallel_index=parallel_index,
        modified_files=modified_files,
        only_test_related=only_test_related,
        only_non_test_related=only_non_test_related,
        dry_run=dry_run,
        build_system=build_system,
        marker_expr=marker_expr,
        filter_expr=filter_expr,
    )
    click.echo(f'Built the following apps in {time.time() - start_time:.2f} seconds:')
    for app in apps:
        line = f'\t{app.build_path} [{app.build_status.value}]'
        if app.build_comment:
            line += f' ({app.build_comment})'
        click.echo(line)

    ctx.exit(ret)


@build.command()
@click.option('--path', help='Path to create the config file')
def init(path: str):
    """Create .idf_build_apps.toml with default values"""
    create_config_file(os.path.join(os.path.dirname(__file__), '..', 'templates', '.idf_build_apps.toml'), path)


@build.command()
@option_paths
@option_output
def collect(
    paths,
    output,
):
    """Collect all applications, corresponding test cases and output the result in JSON format."""
    apps = find_apps(
        paths=paths,
        find_arguments=FindArguments(
            include_all_apps=True,
            recursive=True,
        ),
    )

    test_cases = get_pytest_cases(
        paths=paths,
        target='all',
        additional_args=['--ignore-no-tests-collected-error'],
    )

    # Create a dict with test cases for quick lookup
    # Structure: path -> target -> sdkconfig -> PytestCase
    test_cases_index: dict[str, dict[str, dict[str, PytestCase]]] = {}
    for case in test_cases:
        case_path = Path(case.path).parent.as_posix()
        test_cases_index.setdefault(case_path, {}).setdefault(case.target_selector, {})
        for app in case.apps:
            test_cases_index[case_path][case.target_selector][app.config] = case

    # Example output:
    #
    # {
    #     "projects": {
    #         "path/to/project": [
    #             {
    #                 "target": "esp32",
    #                 "sdkconfig": "release",
    #                 "build_status": "should be built",
    #                 "build_comment": "",
    #                 "test_comment": "",
    #                 "test_cases": [
    #                     "test_case_1",
    #                     "test_case_2"
    #                 ]
    #             }
    #         ]
    #     }
    # }
    result: dict[str, t.Any] = {'projects': {}}

    # Gather apps by path
    apps_by_path: t.Dict[str, t.List[App]] = {}
    for app in apps:
        apps_by_path.setdefault(app.app_dir, []).append(app)

    for index, path in enumerate(sorted(apps_by_path)):
        logger.debug(f'Processing path {index + 1}/{len(apps_by_path)} with {len(apps_by_path[path])} apps: {path}')

        project_path = result['projects'][path] = []

        for app in apps_by_path[path]:
            # Get sdkconfig name from sdkconfig path
            # Example: "sdkconfig.ci.release" -> "release"
            app_sdkconfig_name = Path(app.sdkconfig_path).name.split('.')[-1] if app.sdkconfig_path else 'default'

            app_abs_path = Path(path).absolute().as_posix()

            # Find test cases for current app by path, target and sdkconfig
            app_test_cases: list[PytestCase] = []
            if app_abs_path in test_cases_index:
                if app.target in test_cases_index[app_abs_path]:
                    if app_sdkconfig_name in test_cases_index[app_abs_path][app.target]:
                        app_test_cases.append(test_cases_index[app_abs_path][app.target][app_sdkconfig_name])

            project_path.append(
                {
                    'target': app.target,
                    'sdkconfig': app_sdkconfig_name,
                    'build_status': app.build_status.value,
                    'build_comment': app.build_comment or '',
                    'test_comment': app.test_comment or '',
                    'test_cases': [case.name for case in app_test_cases],
                }
            )

    # Output result to file or stdout
    if output is not None:
        with open(output, 'w') as f:
            json.dump(result, f)
    else:
        click.echo(json.dumps(result))
