# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os

import click

from idf_ci import get_pytest_cases

from ..idf_pytest.models import GroupedPytestCases
from ._options import create_config_file, option_pytest

logger = logging.getLogger(__name__)


@click.group()
def test():
    """Group of test related commands."""
    pass


@test.command()
@click.option('--path', help='Path to create the config file')
def init(path: str):
    """Create pytest.ini with default values."""
    create_config_file(os.path.join(os.path.dirname(__file__), '..', 'templates', 'pytest.ini'), path)


@test.command()
@click.argument('paths', nargs=-1, type=click.Path(dir_okay=True, file_okay=False, exists=True))
@click.option('-t', '--target', default='all', help='Target to be processed. Or "all" to process all targets.')
@option_pytest
@click.option(
    '--format',
    '_format',
    type=click.Choice(['raw', 'github']),
    default='raw',
    help='Output format',
)
@click.option(
    '-o',
    '--output',
    type=click.Path(dir_okay=False, file_okay=True),
    help='Output destination. Stdout if not provided',
)
def collect(
    paths,
    *,
    marker_expr,
    filter_expr,
    target,
    _format,
    output,
):
    """Collect and process pytest cases."""
    grouped_cases = GroupedPytestCases(
        get_pytest_cases(
            paths=paths or ['.'],
            target=target or 'all',
            marker_expr=marker_expr,
            filter_expr=filter_expr,
        )
    )

    if _format == 'raw':
        result = grouped_cases.output_as_string()
    elif _format == 'github':
        result = grouped_cases.output_as_github_ci()
    else:
        raise ValueError(f'Unknown output format: {_format}')

    if output is None:
        click.echo(result)
    else:
        with open(output, 'w') as f:
            f.write(result)
        click.echo(f'Created test cases collection file: {output}')
