# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import io
import logging
import os.path
import typing as t
from contextlib import redirect_stderr, redirect_stdout

import pytest
from _pytest.config import ExitCode

from idf_ci._compat import UNDEF, PathLike, Undefined
from idf_ci.profiles import IniProfileManager

from .models import PytestCase
from .plugin import IdfPytestPlugin

LOGGER = logging.getLogger(__name__)


def get_pytest_cases(
    paths: t.List[str],
    target: str = 'all',
    *,
    profiles: t.List[PathLike] = UNDEF,  # type: ignore
) -> t.List[PytestCase]:
    if isinstance(profiles, Undefined):
        profiles = ['default']

    profile_o = IniProfileManager(
        profiles,
        os.path.join(os.path.dirname(__file__), '..', 'templates', 'default_test_profile.ini'),
    )
    LOGGER.debug('config file: %s', profile_o.merged_profile_path)
    LOGGER.debug('config file content: %s', profile_o.read(profile_o.merged_profile_path))

    with io.StringIO() as out_b, io.StringIO() as err_b:
        with redirect_stdout(out_b), redirect_stderr(err_b):
            plugin = IdfPytestPlugin(cli_target=target)
            res = pytest.main(
                [
                    *paths,
                    '--collect-only',
                    '-c',
                    profile_o.merged_profile_path,
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

    raise RuntimeError(
        f'pytest collection failed at {", ".join(paths)}.\n' f'stdout: {stdout_msg}\n' f'stderr: {stderr_msg}'
    )
