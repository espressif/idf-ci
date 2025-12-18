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
from idf_build_apps.constants import ALL_TARGETS

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
@click.option('--include-only-enabled-apps', is_flag=True, default=False, help='Include only enabled apps')
def collect(
    paths,
    output,
    include_only_enabled_apps,
):
    """Collect all applications, corresponding test cases and output the result in JSON format."""

    apps = find_apps(
        find_arguments=FindArguments(
            paths=paths,
            include_all_apps=not include_only_enabled_apps,
            recursive=True,
            enable_preview_targets=True,
        ),
    )

    test_cases = get_pytest_cases(
        paths=paths,
        marker_expr='',  # pass empty marker to collect all test cases
        additional_args=['--ignore-no-tests-collected-error'],
    )

    # Gather apps by path
    apps_by_path: t.Dict[str, t.List[App]] = {}
    apps_by_abs_path: t.Dict[str, t.List[App]] = {}
    for app in apps:
        apps_by_path.setdefault(app.app_dir, []).append(app)
        apps_by_abs_path.setdefault(Path(app.app_dir).absolute().as_posix(), []).append(app)

    # Create a dict with test cases for quick lookup
    # Structure: path -> target -> sdkconfig -> list[PytestCase]
    test_cases_index: dict[str, dict[str, dict[str, t.List[PytestCase]]]] = {}
    for case in test_cases:
        case_path = Path(case.path).parent.as_posix()

        # Handle multiple targets
        targets = case.targets
        for target in targets:
            test_cases_index.setdefault(case_path, {}).setdefault(target, {})

            for app in case.apps:
                test_cases_index[case_path][target].setdefault(app.config, [])
                test_cases_index[case_path][target][app.config].append(case)

    result: dict[str, t.Any] = {
        'summary': {
            'total_projects': len(apps_by_path),
            'total_apps': len(apps),
            'total_test_cases': len(test_cases),
            'total_test_cases_used': 0,
            'total_test_cases_disabled': 0,
            'total_test_cases_requiring_nonexistent_app': 0,
        },
        'projects': {},
    }

    for index, app_path in enumerate(sorted(apps_by_path)):
        logger.debug(
            f'Processing path {index + 1}/{len(apps_by_path)} with {len(apps_by_path[app_path])} apps: {app_path}'
        )

        project_path = result['projects'][app_path] = {'apps': [], 'test_cases_requiring_nonexistent_app': []}
        project_test_cases: t.Set[str] = set()
        used_test_cases: t.Set[str] = set()
        disabled_test_cases: t.Set[str] = set()
        app_abs_path = Path(app_path).absolute().as_posix()

        for app in apps_by_path[app_path]:
            # Find test cases for current app by path, target and sdkconfig
            app_test_cases: t.Dict[str, PytestCase] = {}

            if app_abs_path in test_cases_index:
                # Gather all test cases
                for target_key in test_cases_index[app_abs_path]:
                    for sdkconfig_key in test_cases_index[app_abs_path][target_key]:
                        test_cases = test_cases_index[app_abs_path][target_key][sdkconfig_key]
                        project_test_cases.update([case.caseid for case in test_cases])

                # Find matching test cases
                if app.target in test_cases_index[app_abs_path]:
                    if app.config_name in test_cases_index[app_abs_path][app.target]:
                        test_cases = test_cases_index[app_abs_path][app.target][app.config_name]

                        for case in test_cases:
                            app_test_cases[case.caseid] = case

            # Get enabled test targets from manifest if exists
            enabled_test_targets = ALL_TARGETS
            if app.MANIFEST is not None:
                enabled_test_targets = app.MANIFEST.enable_test_targets(app_path, config_name=app.config_name)

            # Test cases info
            test_cases = []
            for case in app_test_cases.values():
                test_case = {
                    'name': case.name,
                    'caseid': case.caseid,
                }

                skipped_targets = case.skipped_targets()
                is_disabled_by_manifest = app.target not in enabled_test_targets
                is_disabled_by_marker = app.target in skipped_targets

                if is_disabled_by_manifest or is_disabled_by_marker:
                    test_case['disabled'] = True
                    test_case['disabled_by_manifest'] = is_disabled_by_manifest
                    test_case['disabled_by_marker'] = is_disabled_by_marker

                    if is_disabled_by_marker:
                        test_case['skip_reason'] = skipped_targets[app.target]

                    if is_disabled_by_manifest:
                        test_case['test_comment'] = app.test_comment or ''

                    disabled_test_cases.add(case.caseid)
                else:
                    used_test_cases.add(case.caseid)

                test_cases.append(test_case)

            project_path['apps'].append(
                {
                    'target': app.target,
                    'sdkconfig': app.config_name,
                    'build_status': app.build_status.value,
                    'build_comment': app.build_comment or '',
                    'test_comment': app.test_comment or '',
                    'test_cases': test_cases,
                }
            )

        unused_test_cases = project_test_cases.copy()
        unused_test_cases.difference_update(used_test_cases)
        unused_test_cases.difference_update(disabled_test_cases)

        for case in unused_test_cases:
            project_path['test_cases_requiring_nonexistent_app'].append(case)

        result['summary']['total_test_cases_used'] += len(used_test_cases)
        result['summary']['total_test_cases_disabled'] += len(disabled_test_cases)
        result['summary']['total_test_cases_requiring_nonexistent_app'] += len(unused_test_cases)

    # Output result to file or stdout
    if output is not None:
        with open(output, 'w') as f:
            json.dump(result, f)
    else:
        click.echo(json.dumps(result))
