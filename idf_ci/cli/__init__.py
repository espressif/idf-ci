# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

__all__ = ['click_cli']


import logging
import os
import typing as t
from ast import literal_eval

import click

from idf_ci.cli._options import create_config_file
from idf_ci.cli.build_group import build
from idf_ci.cli.gitlab_group import gitlab
from idf_ci.cli.test_group import test
from idf_ci.settings import _refresh_ci_settings
from idf_ci.utils import setup_logging

logger = logging.getLogger(__name__)


@click.group(context_settings={'show_default': True, 'help_option_names': ['-h', '--help']})
@click.option(
    '-c',
    '--config-file',
    type=click.Path(dir_okay=False, file_okay=True, exists=True),
    help='Path to the idf-ci config file',
)
@click.option(
    '--config',
    type=str,
    multiple=True,
    help=(
        'Override settings via dot-path assignments (repeatable). '
        'Format: path.to.key = value. '
        'Values use Python literal syntax (ast.literal_eval): 10, True, "str", {..}, [..]. '
        'Precedence: CLI > init > config file > defaults'
    ),
)
@click.option('--debug', is_flag=True, default=False, help='Enable debug logging')
def click_cli(config_file, config, debug):
    """ESP-IDF CI CLI Tool."""
    if debug:
        setup_logging(logging.DEBUG)
    else:
        setup_logging()

    overrides_dict = {}
    if config:

        def _set_nested(target: t.Dict, path: str, value: t.Any):
            parts = [p.strip() for p in path.split('.') if p.strip()]
            if not parts:
                raise click.BadParameter('Empty key in --config assignment')

            cursor = target
            for key in parts[:-1]:  # check all but last
                if key not in cursor or not isinstance(cursor.get(key), dict):
                    cursor[key] = {}
                cursor = cursor[key]
            cursor[parts[-1]] = value

        for item in config:  # item like: "a.b = 1"
            left, sep, right = item.partition('=')
            if not sep:
                raise click.BadParameter(f'Invalid --config entry `{item}`. Expected format: `path.to.key = value`')
            try:
                value = literal_eval(right.strip())
            except Exception as e:
                raise click.BadParameter(f'Failed to parse value in --config `{item}`: {e}')

            _set_nested(overrides_dict, left.strip(), value)

    _refresh_ci_settings(config_file, overrides_dict)


@click_cli.command()
@click.option('--path', help='Path to create the config file')
def init(path: str):
    """Create .idf_ci.toml with default values."""
    create_config_file(os.path.join(os.path.dirname(__file__), '..', 'templates', '.idf_ci.toml'), path)


@click_cli.command()
def completions():
    """Instructions to enable shell completions for idf-ci."""
    click.echo("""
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
    """)


click_cli.add_command(build)
click_cli.add_command(test)
click_cli.add_command(gitlab)
