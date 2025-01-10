# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import click


@click.group()
def test():
    """
    Group of test related commands
    """
    pass


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
