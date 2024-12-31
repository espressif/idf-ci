# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil

import click


_CLI_SETTINGS = {
    'show_default': True,
    'help_option_names': ['-h', '--help'],
}


@click.group(context_settings=_CLI_SETTINGS)
def cli():
    pass


###############
# completions #
###############
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


#################
# build_profile #
#################
@cli.group()
def build_profile():
    """
    Manage build profile for idf-build-apps
    """
    pass


@build_profile.command()
@click.option('--path', default=os.getcwd(), help='Path to the build profile')
def init(path: str):
    if os.path.isdir(path):
        # here don't use idf_build_apps.constants.IDF_BUILD_APPS_TOML_FN
        # since idf_build_apps requires idf_path
        # fix it after idf-build-apps support lazy-load variables
        filepath = os.path.join(path, '.idf_build_apps.toml')
    else:
        filepath = path

    shutil.copyfile(os.path.join(os.path.dirname(__file__), 'profiles', 'default_build_profile.toml'), filepath)
    click.echo(f'Created build profile at {filepath}')
