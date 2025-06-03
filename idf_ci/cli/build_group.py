# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import time

import click

from idf_ci.scripts import build as build_cmd

from ._options import (
    create_config_file,
    option_modified_files,
    option_parallel,
    option_paths,
    option_pytest,
    option_target,
)


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
@click.option('--only-test-related', is_flag=True, help='Run build only for test-related apps')
@click.option('--only-non-test-related', is_flag=True, help='Run build only for non-test-related apps')
@click.option('--dry-run', is_flag=True, help='Run build in dry-run mode')
@click.option(
    '--build-system',
    default='cmake',
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
