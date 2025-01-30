# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import io
import logging
import os.path
import typing as t
from contextlib import redirect_stderr, redirect_stdout

import pytest
from _pytest.config import ExitCode

from idf_ci._compat import UNDEF, PathLike
from idf_ci.profiles import get_test_profile

from .models import PytestCase
from .plugin import IdfPytestPlugin

LOGGER = logging.getLogger(__name__)


def get_pytest_cases(
    paths: t.List[str],
    target: str = 'all',
    *,
    profiles: t.List[PathLike] = UNDEF,  # type: ignore
    sdkconfig_name: t.Optional[str] = None,
) -> t.List[PytestCase]:
    test_profile = get_test_profile(profiles)

    plugin = IdfPytestPlugin(cli_target=target, sdkconfig_name=sdkconfig_name)

    with io.StringIO() as out_b, io.StringIO() as err_b:
        with redirect_stdout(out_b), redirect_stderr(err_b):
            res = pytest.main(
                [
                    *paths,
                    '--collect-only',
                    '-c',
                    test_profile.merged_profile_path,
                    '--rootdir',
                    os.getcwd(),
                    '--target',
                    'all',
                ],
                plugins=[plugin],
            )
        stdout_msg = out_b.getvalue()
        stderr_msg = err_b.getvalue()

    if res == ExitCode.OK:
        return plugin.cases

    raise RuntimeError(f'pytest collection failed at {", ".join(paths)}.\nstdout: {stdout_msg}\nstderr: {stderr_msg}')
