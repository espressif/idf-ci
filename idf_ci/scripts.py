# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os.path
import subprocess
import typing as t

from ._compat import UNDEF, PathLike, Undefined
from .profiles import TomlProfileManager


def build(
    paths: t.List[str],
    target: str,
    *,
    profiles: t.List[PathLike] = UNDEF,  # type: ignore
):
    if isinstance(profiles, Undefined):
        profiles = ['default']

    profile_o = TomlProfileManager(
        profiles=profiles,
        default_profile_path=os.path.join(os.path.dirname(__file__), 'templates', 'default_build_profile.toml'),
    )

    print(profile_o.merged_profile_path)

    subprocess.run(
        [
            'idf-build-apps',
            'build',
            '-p',
            *paths,
            '-t',
            target,
            '--config-file',
            profile_o.merged_profile_path,
            '-vvv',
        ],
        check=True,
    )
