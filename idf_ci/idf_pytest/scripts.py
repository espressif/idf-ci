# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import io
import logging
import os.path
import typing as t
from contextlib import redirect_stderr, redirect_stdout

import pytest
from _pytest.config import ExitCode

from idf_ci._compat import UNDEF, Undefined

from ..utils import setup_logging
from .models import PytestCase
from .plugin import IdfPytestPlugin

logger = logging.getLogger(__name__)


def get_pytest_cases(
    paths: t.List[str],
    target: str = 'all',
    *,
    sdkconfig_name: t.Optional[str] = None,
    marker_expr: str = UNDEF,
) -> t.List[PytestCase]:
    if isinstance(marker_expr, Undefined):
        if 'linux' in target:
            marker_expr = 'host_test'
        else:
            marker_expr = 'not host_test'

    plugin = IdfPytestPlugin(
        cli_target=target,
        sdkconfig_name=sdkconfig_name,
    )
    args = [
        *paths,
        '--collect-only',
        '--rootdir',
        os.getcwd(),
        '--target',
        target,
    ]
    if marker_expr:
        args.extend(['-m', f'{marker_expr}'])

    cur_log_level = logger.parent.level  # type: ignore

    with io.StringIO() as out_b, io.StringIO() as err_b:
        with redirect_stdout(out_b), redirect_stderr(err_b):
            res = pytest.main(args, plugins=[plugin])
        stdout_msg = out_b.getvalue()
        stderr_msg = err_b.getvalue()

    setup_logging(level=cur_log_level)  # the redirect messes up the logging level

    if res == ExitCode.OK:
        return plugin.cases

    raise RuntimeError(f'pytest collection failed.\nArgs: {args}\nStdout: {stdout_msg}\nStderr: {stderr_msg}')
