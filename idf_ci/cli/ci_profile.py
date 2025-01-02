# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import click


@click.group()
def ci_profile():
    """
    Group of commands for managing CI profiles for idf-ci
    """
    pass


@ci_profile.command()
@click.option('--path', default=os.getcwd(), help='Path to create the CI profile')
def init(path: str):
    """
    Create a CI profile at the given folder
    """
    if os.path.isdir(path):
        filepath = os.path.join(path, '.idf_ci.toml')
    else:
        filepath = path

    shutil.copyfile(os.path.join(os.path.dirname(__file__), '..', 'profiles', 'default_ci_profile.toml'), filepath)
    click.echo(f'Created CI profile at {filepath}')
