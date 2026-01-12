# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from idf_ci import CiSettings


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_dir(tmp_path: Path) -> str:
    return str(tmp_path)


@pytest.fixture(autouse=True)
def reset_settings(tmp_path):
    CiSettings.CONFIG_FILE_PATH = None

    curdir = os.getcwd()
    os.chdir(tmp_path)

    yield

    os.chdir(curdir)


def create_project(name: str, folder: Path) -> Path:
    p = folder / name
    p.mkdir(parents=True, exist_ok=True)
    (p / 'main').mkdir(parents=True, exist_ok=True)

    with open(p / 'CMakeLists.txt', 'w') as fw:
        fw.write(
            f"""cmake_minimum_required(VERSION 3.16)
include($ENV{{IDF_PATH}}/tools/cmake/project.cmake)
project({name})
"""
        )

    with open(p / 'main' / 'CMakeLists.txt', 'w') as fw:
        fw.write(
            f"""idf_component_register(SRCS "{name}.c"
INCLUDE_DIRS ".")
"""
        )

    with open(p / 'main' / f'{name}.c', 'w') as fw:
        fw.write(
            """#include <stdio.h>
void app_main(void) {}
"""
        )

    return p
