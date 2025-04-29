# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import os
import subprocess
import tempfile
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


@pytest.fixture
def sample_test_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create pytest.ini with env_markers
        with open(os.path.join(tmpdir, 'pytest.ini'), 'w') as f:
            f.write("""
[pytest]
env_markers =
    generic: applicable to generic ESP devices
    host_test: this test case runs on host machines
""")

        # Create the test file
        test_file_path = os.path.join(tmpdir, 'test_sample.py')
        with open(test_file_path, 'w') as f:
            f.write(TEST_FILE_CONTENT)

        yield test_file_path


class TestCollectFunction:
    @pytest.fixture(autouse=True)
    def setup_test_project(self, tmp_path, test_case_name):
        create_project('sample', tmp_path)
        with open('pytest.ini', 'w') as f:
            f.write("""
[pytest]
env_markers =
    generic: applicable to generic ESP devices
    multiboard: test case runs on multiple ESP devices
""")
        with open(f'{test_case_name}.py', 'w') as f:
            f.write(TEST_FILE_CONTENT)

    def test_output_as_string(self):
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
                encoding='utf8',
            ).strip()
        )

    def test_output_as_github_ci(self, test_case_name):
        assert {
            'include': [
                {
                    'targets': 'esp32',
                    'env_markers': 'generic',
                    'runner_tags': ['self-hosted', 'esp32', 'generic'],
                    'nodes': f'{test_case_name}.py::test_single_target[esp32]',
                },
                {
                    'targets': 'linux',
                    'env_markers': 'generic',
                    'runner_tags': ['self-hosted', 'linux', 'generic'],
                    'nodes': f'{test_case_name}.py::test_single_target[linux]',
                },
                {
                    'targets': 'esp32',
                    'env_markers': '',
                    'runner_tags': ['self-hosted', 'esp32'],
                    'nodes': f'{test_case_name}.py::test_single_target_qemu[esp32]',
                },
                {
                    'targets': 'esp32c3',
                    'env_markers': '',
                    'runner_tags': ['self-hosted', 'esp32c3'],
                    'nodes': f'{test_case_name}.py::test_single_target_qemu[esp32c3]',
                },
                {
                    'targets': 'esp32,esp32s2',
                    'env_markers': 'multiboard',
                    'runner_tags': ['self-hosted', 'esp32+esp32s2', 'multiboard'],
                    'nodes': f'{test_case_name}.py::test_multi_dut[2-esp32|esp32s2]',
                },
                {
                    'targets': 'esp32,esp32,esp32s2',
                    'env_markers': 'multiboard',
                    'runner_tags': ['self-hosted', 'esp32_2+esp32s2', 'multiboard'],
                    'nodes': f'{test_case_name}.py::test_multi_dut[3-esp32|esp32|esp32s2]',
                },
                {
                    'targets': 'linux,linux',
                    'env_markers': 'multiboard',
                    'runner_tags': ['self-hosted', 'linux_2', 'multiboard'],
                    'nodes': f'{test_case_name}.py::test_multi_dut[2-linux]',
                },
            ]
        } == json.loads(
            subprocess.check_output(
                ['idf-ci', 'test', 'collect', '--format', 'github', '--marker-expr', ''],
                encoding='utf8',
            ).strip()
        )  # ensure the output is valid JSON
