# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os

import click

from ._options import create_config_file


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
    create_config_file(os.path.join(os.path.dirname(__file__), '..', 'templates', 'pytest.ini'), path)
