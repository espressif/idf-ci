# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import difflib
import logging
import os
import shutil
import typing as t

import click

from idf_ci._compat import UNDEF

logger = logging.getLogger(__name__)


########################
# Validation Functions #
########################
def _semicolon_separated_list(ctx, param, value):  # noqa: ARG001
    if value is None:
        return None

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
        callback=lambda ctx, param, value: [os.getcwd()] if not value else value,  # noqa: ARG005
    )(func)


def option_target(func):
    return click.option(
        '--target', '-t', default='all', help='Target to be processed. Or "all" to process all targets.'
    )(func)


def option_parallel(func):
    func = click.option('--parallel-count', default=1, help='Number of parallel builds')(func)
    func = click.option('--parallel-index', default=1, help='Index of the parallel build')(func)
    return func


def option_pytest(func):
    func = click.option('-m', '--marker-expr', default=UNDEF, help='Pytest marker expression, "-m" option')(func)
    func = click.option('-k', '--filter-expr', help='Pytest filter expression, "-k" option')(func)
    return func


def option_modified_files(func):
    return click.option(
        '--modified-files',
        help='Semicolon separated list of files that have been modified',
        callback=_semicolon_separated_list,
    )(func)


def option_commit_sha(func):
    return click.option(
        '--commit-sha',
        help=(
            'Commit SHA to download artifacts from. If not provided, will try to get it from: '
            '1) PIPELINE_COMMIT_SHA env var, 2) latest commit from branch.'
        ),
    )(func)


def option_branch(func):
    return click.option(
        '--branch',
        help='Git branch to use. If not provided, will use current git branch.',
    )(func)


#########
# Utils #
#########
def create_config_file(template_filepath: str, dest: t.Optional[str] = None) -> str:
    """Create a configuration file from a template.

    If the destination file already exists, shows a diff between the existing file and
    the template. If they're identical, notifies the user without making changes.

    :param template_filepath: Path to the template file
    :param dest: Path to the destination file or directory

    :returns: Path to the created or existing file
    """
    if dest is None:
        dest = os.getcwd()

    if os.path.isdir(dest):
        filepath = os.path.join(dest, os.path.basename(template_filepath))
    else:
        filepath = dest

    if not os.path.isfile(filepath):
        shutil.copyfile(template_filepath, filepath)
        click.echo(f'Created {filepath}')
        return filepath

    with open(template_filepath) as template_file:
        template_content = template_file.readlines()
    with open(filepath) as existing_file:
        existing_content = existing_file.readlines()

    diff = list(difflib.unified_diff(existing_content, template_content, fromfile='existing', tofile='template'))
    if not diff:
        click.secho(f'{filepath} already exists and is identical to the template.', fg='yellow')
        return filepath

    click.secho(f'{filepath} already exists. Showing diff:', fg='yellow')
    for line in diff:
        if line.startswith('+'):
            click.secho(line, fg='green', nl=False)
        elif line.startswith('-'):
            click.secho(line, fg='red', nl=False)
        elif line.startswith('@@'):
            click.secho(line, fg='cyan', nl=False)
        else:
            click.secho(line, nl=False)

    return filepath
