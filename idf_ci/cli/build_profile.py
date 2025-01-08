# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import click


@click.group()
def build_profile():
    """
    Group of commands for managing build profiles for idf-build-apps
    """
    pass


@build_profile.command()
@click.option('--path', default=os.getcwd(), help='Path to create the build profile')
def init(path: str):
    """
    Create a build profile at the given folder
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
