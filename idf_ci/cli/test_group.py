# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os

import click

from idf_ci import get_pytest_cases

from ..idf_pytest.models import GroupedPytestCases
from ._options import create_config_file

logger = logging.getLogger(__name__)


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


@test.command()
@click.argument('paths', nargs=-1, type=click.Path(dir_okay=False, file_okay=True, exists=True))
@click.option('-m', '--marker-expr', default='not host_test', help='Pytest marker expression')
@click.option('-t', '--target', default='all', help='Target to be processed. Or "all" to process all targets.')
@click.option(
    '--format',
    '_format',
    type=click.Choice(
        [
            'raw',
            'github',
            # 'gitlab',  # TODO
        ]
    ),
    default='raw',
    help='Output format',
)
@click.option(
    '-o',
    '--output',
    type=click.Path(dir_okay=False, file_okay=True),
    help='Output destination. Stdout if not provided',
)
def collect(paths, *, marker_expr, target, _format, output):
    """
    Run pytest with provided arguments
    """
    logger.debug(f'Collecting test cases from {paths} with target {target} and marker expression {marker_expr}')

    cases = get_pytest_cases(
        paths=paths or ['.'],
        target=target or 'all',
        marker_expr=marker_expr,
    )

    grouped_cases = GroupedPytestCases(cases)

    if _format == 'raw':
        s = grouped_cases.output_as_string()
    elif _format == 'github':
        s = grouped_cases.output_as_github_ci()
    elif _format == 'gitlab':
        s = grouped_cases.output_as_gitlab_ci()
    else:
        raise ValueError(f'Unknown output format: {_format}')

    if output is None:
        click.echo(s)
    else:
        with open(output, 'w') as f:
            f.write(s)

        click.echo(f'Created test cases collection file: {output}')
