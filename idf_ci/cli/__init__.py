# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
import shutil

import click

from .build import build
from .test import test

_CLI_SETTINGS = {
    'show_default': True,
    'help_option_names': ['-h', '--help'],
}


@click.group(context_settings=_CLI_SETTINGS)
def cli():
    pass


@cli.command()
@click.option('--path', default=os.getcwd(), help='Path to create the CI profile')
def init_profile(path: str):
    """
    Create .idf_ci.toml with default values at the given folder
    """
    if os.path.isdir(path):
        filepath = os.path.join(path, '.idf_ci.toml')
    else:
        filepath = path

    shutil.copyfile(os.path.join(os.path.dirname(__file__), '..', 'templates', 'default_ci_profile.toml'), filepath)
    click.echo(f'Created CI profile at {filepath}')


@cli.command()
def completions():
    """
    Instructions to enable shell completions for idf-ci
    """

    help_message = """
    To enable autocomplete run the following command:

    Bash:
      1. Run this command once

        _IDF_CI_COMPLETE=bash_source idf-ci > ~/.idf-ci-complete.bash

      2. Add the following line to your .bashrc
        . ~/.idf-ci-complete.bash

    Zsh:
      1. Run this command once

        _IDF_CI_COMPLETE=zsh_source idf-ci > ~/.idf-ci-complete.zsh

      2. Add the following line to your .zshrc

        . ~/.idf-ci-complete.zsh

    Fish:
      1. Run this command once

        _IDF_CI_COMPLETE=fish_source idf-ci > ~/.config/fish/completions/idf-ci.fish

    After modifying the shell config, you need to start a new shell in order for the changes to be loaded.
    """
    click.echo(help_message)


cli.add_command(build)
cli.add_command(test)


__all__ = ['cli']
