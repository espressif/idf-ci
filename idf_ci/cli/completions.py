# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import click


@click.command()
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
