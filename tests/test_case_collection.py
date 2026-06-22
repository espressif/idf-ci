# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import textwrap

import pytest
from conftest import create_project

# Sample test file content to create for testing
TEST_FILE_CONTENT = """
import pytest

@pytest.mark.parametrize('target', ['esp32', 'linux'], indirect=True)
@pytest.mark.generic
def test_single_target(dut) -> None:
    pass

@pytest.mark.parametrize('target', ['esp32', 'esp32c3'], indirect=True)
@pytest.mark.qemu
def test_single_target_qemu(dut) -> None:
    pass

@pytest.mark.parametrize(
    'count, target',
    [
        (2, 'esp32|esp32s2'),
        (3, 'esp32|esp32|esp32s2'),
        (2, 'linux'),
    ],
)
@pytest.mark.multiboard
def test_multi_dut(dut) -> None:
    pass
"""


# in total should be
# esp32 - generic:
#   test_single_target
# linux - generic:
#   test_single_target
# esp32 - qemu:
#   test_single_target_qemu
# esp32c3 - qemu:
#   test_single_target_qemu
# esp32,esp32s2 - multiboard:
#   test_multi_dut
# esp32,esp32,esp32s2 - multiboard:
#   test_multi_dut
# linux,linux - multiboard:
#   test_multi_dut


class TestCollectFunction:
    @pytest.fixture(autouse=True)
    def setup_test_project(self, pytester):
        create_project('sample', pytester.path)
        with open(pytester.path / 'pytest.ini', 'w') as f:
            f.write("""
[pytest]
env_markers =
    generic: applicable to generic ESP devices
    multiboard: test case runs on multiple ESP devices
    qemu: test case runs on qemu
""")
        with open(pytester.path / 'test_sample.py', 'w') as f:
            f.write(TEST_FILE_CONTENT)

    def test_output_as_string(self, pytester):
        assert (
            textwrap.dedent("""
                esp32 - generic: 1 cases
                \tesp32.default.test_single_target
                esp32,esp32s2 - multiboard: 1 cases
                \t('esp32', 'esp32s2').('default', 'default').test_multi_dut
                esp32,esp32,esp32s2 - multiboard: 1 cases
                \t('esp32', 'esp32', 'esp32s2').('default', 'default', 'default').test_multi_dut
            """).strip()
            == subprocess.check_output(
                ['idf-ci', 'test', 'collect'],
                cwd=pytester.path,
                encoding='utf8',
            ).strip()
        )

    def test_output_as_github_ci(self, pytester):
        assert {
            'include': [
                {
                    'targets': 'esp32',
                    'env_markers': 'generic',
                    'runner_tags': ['self-hosted', 'esp32', 'generic'],
                    'nodes': 'test_sample.py::test_single_target[esp32]',
                },
                {
                    'targets': 'linux',
                    'env_markers': 'generic',
                    'runner_tags': ['self-hosted', 'generic', 'linux'],
                    'nodes': 'test_sample.py::test_single_target[linux]',
                },
                {
                    'targets': 'esp32',
                    'env_markers': 'qemu',
                    'runner_tags': ['self-hosted', 'esp32', 'qemu'],
                    'nodes': 'test_sample.py::test_single_target_qemu[esp32-idf,qemu]',
                },
                {
                    'targets': 'esp32c3',
                    'env_markers': 'qemu',
                    'runner_tags': ['self-hosted', 'esp32c3', 'qemu'],
                    'nodes': 'test_sample.py::test_single_target_qemu[esp32c3-idf,qemu]',
                },
                {
                    'targets': 'esp32,esp32s2',
                    'env_markers': 'multiboard',
                    'runner_tags': ['self-hosted', 'esp32', 'esp32s2', 'multiboard'],
                    'nodes': 'test_sample.py::test_multi_dut[2-esp32|esp32s2]',
                },
                {
                    'targets': 'esp32,esp32,esp32s2',
                    'env_markers': 'multiboard',
                    'runner_tags': ['self-hosted', 'esp32_2', 'esp32s2', 'multiboard'],
                    'nodes': 'test_sample.py::test_multi_dut[3-esp32|esp32|esp32s2]',
                },
                {
                    'targets': 'linux,linux',
                    'env_markers': 'multiboard',
                    'runner_tags': ['self-hosted', 'linux_2', 'multiboard'],
                    'nodes': 'test_sample.py::test_multi_dut[2-linux]',
                },
            ]
        } == json.loads(
            subprocess.check_output(
                ['idf-ci', 'test', 'collect', '--format', 'github', '--marker-expr', ''],
                cwd=pytester.path,
                encoding='utf8',
            ).strip()
        )  # ensure the output is valid JSON
