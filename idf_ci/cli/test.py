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
@click.option('--path', help='Path to create the config file')
def init(path: str):
    """
    Create pytest.ini with default values
    """
    if path is None:
        path = os.getcwd()

    if os.path.isdir(path):
        filepath = os.path.join(path, 'pytest.ini')
    else:
        filepath = path

    shutil.copyfile(os.path.join(os.path.dirname(__file__), '..', 'templates', 'pytest.ini'), filepath)
    click.echo(f'Created {filepath}')
