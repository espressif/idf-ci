# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import click

from idf_ci import build as build_cmd

from ._options import option_paths, option_profiles


@click.group()
def build():
    """
    Group of build related commands
    """
    pass


@build.command()
@option_paths
@click.option('--target', '-t', default='all', help='Target to be built. Or "all" to build all targets.')
@option_profiles
def run(paths, target, profiles):
    """
    Run build according to the given profiles
    """
    click.echo(f'Building {target} with profiles {profiles} at {paths}')
    build_cmd(paths, target, profiles=profiles)


@build.command()
@click.option('--path', default=os.getcwd(), help='Path to create the build profile')
def init_profile(path: str):
    """
    Create .idf_build_apps.toml with default values at the given folder
    """
    if os.path.isdir(path):
        # here don't use idf_build_apps.constants.IDF_BUILD_APPS_TOML_FN
        # since idf_build_apps requires idf_path
        # fix it after idf-build-apps support lazy-load variables
        filepath = os.path.join(path, '.idf_build_apps.toml')
    else:
        filepath = path

    shutil.copyfile(os.path.join(os.path.dirname(__file__), '..', 'templates', 'default_build_profile.toml'), filepath)
    click.echo(f'Created build profile at {filepath}')
