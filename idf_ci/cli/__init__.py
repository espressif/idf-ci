# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import click

from .build_profile import build_profile
from .ci_profile import ci_profile
from .completions import completions

_CLI_SETTINGS = {
    'show_default': True,
    'help_option_names': ['-h', '--help'],
}


@click.group(context_settings=_CLI_SETTINGS)
def cli():
    pass


cli.add_command(build_profile)
cli.add_command(ci_profile)
cli.add_command(completions)


__all__ = ['cli']
