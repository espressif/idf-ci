# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import os
import shutil
import subprocess
import sys
import textwrap

import minio
import pytest
import requests

from idf_ci.cli import click_cli
from idf_ci.idf_gitlab import ArtifactManager
from idf_ci.idf_gitlab.api import S3Error


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
        (build_dir / 'optional.txt').write_text('Optional content', encoding='utf-8')

        return build_dir

    @pytest.fixture(autouse=True)
    def setup_test_dir(self, tmp_path, tmp_dir, monkeypatch):
        (tmp_path / '.idf_ci.toml').write_text(
            textwrap.dedent("""
                [gitlab]
                project = "espressif/esp-idf"

                [gitlab.artifacts.s3.debug]
                bucket = "test-bucket"
                patterns = ["**/build*/build.log"]

                [gitlab.artifacts.s3.flash]
                bucket = "test-bucket"
                patterns = ["**/build*/*.bin"]

                [gitlab.artifacts.s3.metrics]
                bucket = "test-bucket"
                patterns = ["**/build*/size.json"]

                [gitlab.artifacts.s3.optional]
                bucket = "test-bucket"
                patterns = ["**/build*/optional.txt"]
                if_clause = 'ENV_VAR_FOO == "foo"'
            """)
        )

        curdir = os.getcwd()
        os.chdir(tmp_path)

        monkeypatch.setenv('IDF_S3_SERVER', 'http://localhost:9100')
        monkeypatch.setenv('IDF_S3_ACCESS_KEY', 'minioadmin')
        monkeypatch.setenv('IDF_S3_SECRET_KEY', 'minioadmin')

        monkeypatch.setenv('IDF_PATH', tmp_dir)

        yield

        os.chdir(curdir)

    @pytest.fixture
    def s3_client(self) -> minio.Minio:
        client = ArtifactManager().s3_client
        assert client is not None

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

    @pytest.mark.parametrize(
        'set_env_var_foo',
        [
            True,
            False,
        ],
    )
    def test_cli_upload_download_artifacts(
        self, s3_client, tmp_path, sample_artifacts_dir, monkeypatch, set_env_var_foo
    ):
        # in this test we use subprocess, since env var is monkeypatched

        # Mock git functions that would be called
        commit_sha = 'cli_test_sha_123'

        if set_env_var_foo:
            monkeypatch.setenv('ENV_VAR_FOO', 'foo')

        # Upload artifacts
        subprocess.run(
            [
                'idf-ci',
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'flash',
            ],
            check=True,
        )
        objs = list(s3_client.list_objects('test-bucket', recursive=True))
        assert len(objs) == 1
        assert objs[0].object_name == f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/test.bin'

        # upload optional
        subprocess.run(
            [
                'idf-ci',
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'optional',
            ],
            check=True,
        )
        objs = list(s3_client.list_objects('test-bucket', recursive=True))
        if set_env_var_foo:
            assert len(objs) == 2
            assert objs[0].object_name == f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/optional.txt'
        else:
            assert len(objs) == 1
            assert objs[0].object_name == f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/test.bin'

        shutil.rmtree(sample_artifacts_dir)

        # download and check if the files were uploaded
        subprocess.run(
            [
                'idf-ci',
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'flash',
                str(tmp_path),
            ],
            check=True,
        )

        assert sorted(os.listdir(sample_artifacts_dir)) == ['test.bin']
        assert open(sample_artifacts_dir / 'test.bin').read() == 'Binary content'

        # generate presigned URL
        presigned_urls = ArtifactManager().generate_presigned_json(
            commit_sha=commit_sha,
            artifact_type='flash',
        )

        # Save presigned URLs to a file
        presigned_json_path = os.path.join(tmp_path, 'presigned.json')
        with open(presigned_json_path, 'w') as f:
            json.dump(presigned_urls, f)

        # Remove S3 credentials
        monkeypatch.delenv('IDF_S3_ACCESS_KEY')

        # Try to download using presigned.json
        subprocess.run(
            [
                'idf-ci',
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
                '--presigned-json',
                presigned_json_path,
                str(tmp_path),
            ],
            check=True,
        )

        assert os.path.exists(os.path.join(tmp_path, 'app/build_esp32_build/test.bin'))

    def test_cli_generate_presigned_json(self, runner):
        # Mock git functions that would be called
        commit_sha = 'cli_test_sha_123'

        # First upload some artifacts
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

        # Generate presigned URLs
        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'generate-presigned-json',
                '--commit-sha',
                commit_sha,
                '--type',
                'flash',
            ],
        )
        assert result.exit_code == 0

        # Parse the output JSON
        presigned_urls = json.loads(result.output)
        assert len(presigned_urls) == 1
        assert 'app/build_esp32_build/test.bin' in presigned_urls

        # Verify the presigned URL is valid by downloading the file
        response = requests.get(presigned_urls['app/build_esp32_build/test.bin'])
        assert response.status_code == 200
        assert response.text == 'Binary content'

    def test_download_without_s3_credentials(self, runner, tmp_path, monkeypatch):
        # Remove S3 credentials
        monkeypatch.delenv('IDF_S3_ACCESS_KEY')

        # Try to download artifacts
        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                'test_sha',
                '--type',
                'flash',
                str(tmp_path),
            ],
        )

        assert result.exit_code != 0
        assert isinstance(result.exception, S3Error)
        assert 'Configure S3 storage to download artifacts' in result.exception.args

    def test_upload_without_s3_credentials(self, runner, tmp_path, monkeypatch):
        # Remove S3 credentials
        monkeypatch.delenv('IDF_S3_ACCESS_KEY')

        # Try to upload artifacts
        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                'test_sha',
                '--type',
                'flash',
                str(tmp_path),
            ],
        )

        assert result.exit_code != 0
        assert isinstance(result.exception, S3Error)
        assert 'Configure S3 storage to upload artifacts' in result.exception.args
