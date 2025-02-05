# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import click

from idf_ci._compat import Undefined
from idf_ci.scripts import test as test_cmd
from idf_ci.settings import CiSettings

from ._options import option_parallel, option_paths, option_profiles, option_target


@click.group()
def test():
    """
    Group of test related commands
    """
    pass


@test.command()
@option_paths
@option_target
@option_profiles
@option_parallel
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show the test cases instead of running them',
)
def run(*, paths, target, profiles, parallel_count, parallel_index, dry_run):
    """
    Run tests according to the given profiles
    """
    if not isinstance(profiles, Undefined):
        pass
    else:
        profiles = CiSettings().test_profiles

    click.echo(f'Building {target} with profiles {profiles} at {paths}')
    test_cmd(
        paths,
        target,
        profiles=profiles,
        parallel_count=parallel_count,
        parallel_index=parallel_index,
        dry_run=dry_run,
    )


@test.command()
@click.option('--path', default=os.getcwd(), help='Path to create the CI profile')
def init_profile(path: str):
    """
    Create pytest.ini with default values at the given folder
    """
    if os.path.isdir(path):
        filepath = os.path.join(path, 'pytest.ini')
    else:
        filepath = path

    shutil.copyfile(os.path.join(os.path.dirname(__file__), '..', 'templates', 'default_test_profile.ini'), filepath)
    click.echo(f'Created test profile at {filepath}')
