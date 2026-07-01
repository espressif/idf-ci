# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from idf_ci.scripts import upload_app_sizes


@pytest.fixture(autouse=True)
def setup_infra_dashboard_env(monkeypatch):
    monkeypatch.setenv('INFRA_DASHBOARD_API_URL', 'http://custom-url/api')
    monkeypatch.setenv('INFRA_DASHBOARD_PROJECT_ID', '1')


@pytest.fixture
def build_summary_file(tmp_path):
    dest = tmp_path / 'build_summary.xml'
    shutil.copy(
        Path(__file__).parent / 'fixtures' / 'build_summary.xml',
        dest,
    )
    return dest


def test_upload_app_sizes_success(build_summary_file):
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        count = upload_app_sizes(
            pattern=str(build_summary_file),
            job_token='my-job-token',
            commit_sha='a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        )

        assert count == 1
        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        called_json = mock_post.call_args[1]['json']
        called_headers = mock_post.call_args[1]['headers']

        assert called_url == 'http://custom-url/api/project/1/app/size'
        assert called_headers['Job-Token'] == 'my-job-token'
        assert len(called_json) == 1
        assert called_json[0] == {
            'app_path': 'examples/get-started/hello_world',
            'target': 'esp32',
            'config': 'default',
            'total_size': 124759,
            'commit_sha': 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        }


def test_upload_app_sizes_private_token_success(build_summary_file):
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        count = upload_app_sizes(
            pattern=str(build_summary_file),
            private_token='my-private-token',
            commit_sha='a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        )

        assert count == 1
        mock_post.assert_called_once()
        called_headers = mock_post.call_args[1]['headers']

        assert called_headers['Private-Token'] == 'my-private-token'
        assert 'Job-Token' not in called_headers


def test_upload_app_sizes_both_tokens_precedence(build_summary_file):
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        count = upload_app_sizes(
            pattern=str(build_summary_file),
            job_token='my-job-token',
            private_token='my-private-token',
            commit_sha='a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2',
        )

        assert count == 1
        mock_post.assert_called_once()
        called_headers = mock_post.call_args[1]['headers']
        assert called_headers['Job-Token'] == 'my-job-token'
        assert 'Private-Token' not in called_headers
