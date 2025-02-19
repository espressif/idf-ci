# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import functools
import os

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
        default=[os.getcwd()],
        multiple=True,
        type=click.Path(dir_okay=True, file_okay=False, exists=True),
        help=_OPTION_PATHS_HELP,
    )(func)


def option_target(func):
    return click.option(
        '--target', '-t', default='all', help='Target to be processed. Or "all" to process all targets.'
    )(func)


def option_parallel(func):
    @click.option('--parallel-count', default=1, help='Number of parallel builds')
    @click.option('--parallel-index', default=1, help='Index of the parallel build')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def option_modified_files(func):
    return click.option(
        '--modified-files',
        help='Semicolon separated list of files that have been modified',
        callback=_semicolon_separated_list,
    )(func)
