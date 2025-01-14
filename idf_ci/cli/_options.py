# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import click

from idf_ci._compat import UNDEF


########################
# Validation Functions #
########################
def _semicolon_separated_list(ctx, param, value):  # noqa: ARG001
    if value is None:
        return UNDEF

    if not isinstance(value, str):
        raise click.BadParameter('Value must be a string')

    return [v.strip() for v in value.split(';') if v.strip()]


###########
# Options #
###########
_OPTION_PATHS_HELP = """
List of directories to process. Support passing multiple times.

\b
Example:
    --paths component_1 --paths component_2
    -p component_1 -p component_2
"""


def option_paths(func):
    return click.option(
        '--paths',
        '-p',
        multiple=True,
        type=click.Path(dir_okay=True, file_okay=False, exists=True),
        help=_OPTION_PATHS_HELP,
    )(func)


_OPTION_PROFILES_HELP = """
\b
List of profiles to apply. Could be "default" or file path to a custom profile.
Support passing multiple times. The later profiles will override the previous ones.
[default: default]

\b
Example:
  --profiles default;custom.toml  # To apply default and custom profiles
  --profiles ';'  # To unset the default profile
"""


def option_profiles(func):
    return click.option(
        '--profiles',
        help=_OPTION_PROFILES_HELP,
        callback=_semicolon_separated_list,
    )(func)
