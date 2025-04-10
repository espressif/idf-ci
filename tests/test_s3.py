# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import shutil
import sys
import textwrap

import minio
import pytest

from idf_ci.cli import click_cli
from idf_ci.idf_gitlab.s3 import create_s3_client


# to run this test, don't forget to run "docker compose up -d" in the root directory of the project
@pytest.mark.skipif(sys.platform == 'win32', reason='minio service not available on Windows')
class TestUploadDownloadArtifacts:
    @pytest.fixture
    def sample_artifacts_dir(self, tmp_path):
        build_dir = tmp_path / 'app' / 'build_esp32_build'
        build_dir.mkdir(parents=True)

        # Create some test files
        (build_dir / 'build.log').write_text('Test build log', encoding='utf-8')
        (build_dir / 'test.bin').write_text('Binary content', encoding='utf-8')
        (build_dir / 'size.json').write_text('{"size": 1024}', encoding='utf-8')

        return build_dir

    @pytest.fixture(autouse=True)
    def setup_test_dir(self, tmp_path, tmp_dir, monkeypatch):
        (tmp_path / '.idf_ci.toml').write_text(
            textwrap.dedent("""
                [gitlab]
                project = "espressif/esp-idf"

                [gitlab.artifact]
                debug_filepatterns = [
                    '**/build*/build.log',  # build_log_filename
                ]
                flash_filepatterns = [
                    '**/build*/*.bin',
                ]
                metrics_filepatterns = [
                    '**/build*/size.json',  # size_json_filename
                ]
            """)
        )

        monkeypatch.setenv('IDF_S3_BUCKET', 'test-bucket')
        monkeypatch.setenv('IDF_S3_SERVER', 'http://localhost:9100')
        monkeypatch.setenv('IDF_S3_ACCESS_KEY', 'minioadmin')
        monkeypatch.setenv('IDF_S3_SECRET_KEY', 'minioadmin')

        monkeypatch.setenv('IDF_PATH', tmp_dir)

    @pytest.fixture
    def s3_client(self):
        client = create_s3_client()
        # Drop and recreate bucket before test
        try:
            for obj in client.list_objects('test-bucket', recursive=True):
                client.remove_object('test-bucket', obj.object_name)

            client.remove_bucket('test-bucket')
        except minio.error.S3Error as e:
            logging.error(f'Error removing bucket: {e}')
            pass
        client.make_bucket('test-bucket')
        return client

    def test_cli_upload_download_artifacts(self, s3_client, runner, tmp_path, sample_artifacts_dir):
        # Mock git functions that would be called
        commit_sha = 'cli_test_sha_123'

        # upload
        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'flash',
            ],
        )
        assert result.exit_code == 0
        objs = list(s3_client.list_objects('test-bucket', recursive=True))
        assert len(objs) == 1
        assert objs[0].object_name == f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/test.bin'

        shutil.rmtree(sample_artifacts_dir)

        # download and check if the files were uploaded
        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'flash',
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0
        assert sorted(os.listdir(sample_artifacts_dir)) == ['test.bin']
        assert open(sample_artifacts_dir / 'test.bin').read() == 'Binary content'
