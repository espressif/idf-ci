# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os.path
import subprocess
import typing as t

from ._compat import UNDEF, PathLike, Undefined
from .profiles import TomlProfileManager
from .settings import CiSettings


def build(
    paths: t.List[str],
    target: str,
    *,
    profiles: t.List[PathLike] = UNDEF,  # type: ignore
    parallel_count: int = 1,
    parallel_index: int = 1,
    modified_files: t.Optional[t.List[str]] = None,
):
    if isinstance(profiles, Undefined):
        profiles = ['default']

    profile_o = TomlProfileManager(
        profiles=profiles,
        default_profile_path=os.path.join(os.path.dirname(__file__), 'templates', 'default_build_profile.toml'),
    )

    args = [
        'idf-build-apps',
        'build',
        '-p',
        *paths,
        '-t',
        target,
        '--config-file',
        profile_o.merged_profile_path,
        '-v',
        '--parallel-count',
        str(parallel_count),
        '--parallel-index',
        str(parallel_index),
    ]

    if modified_files is not None:
        modified_components = CiSettings().get_modified_components(modified_files)
        args.extend(
            [
                '--modified-files',
                *modified_files,
                '--modified-components',
                *modified_components,
            ]
        )

    subprocess.run(
        args,
        check=True,
    )
