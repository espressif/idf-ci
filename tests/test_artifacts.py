# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import os
import shutil
import sys
import textwrap

import minio
import pytest
import requests

from idf_ci.cli import click_cli
from idf_ci.idf_gitlab import ArtifactManager
from idf_ci.idf_gitlab.api import S3Error
from idf_ci.settings import _refresh_ci_settings


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
        (tmp_path / 'optional.txt').write_text('Optional content', encoding='utf-8')

        return build_dir

    @pytest.fixture(autouse=True)
    def setup_test_dir(self, tmp_path, tmp_dir, monkeypatch):
        (tmp_path / '.idf_ci.toml').write_text(
            textwrap.dedent("""
                [gitlab]
                project = "espressif/esp-idf"

                [gitlab.artifacts.s3]
                enable = true

                [gitlab.artifacts.s3.configs.debug]
                bucket = "private"
                base_dir_pattern = "**/build*/"
                file_patterns = ["build.log"]

                [gitlab.artifacts.s3.configs.flash]
                bucket = "private"
                base_dir_pattern = "**/build*/"
                file_patterns = ["*.bin"]

                [gitlab.artifacts.s3.configs.metrics]
                bucket = "private"
                zip_first = false
                base_dir_pattern = "**/build*/"
                file_patterns = ["size.json"]

                [gitlab.artifacts.s3.configs.optional]
                bucket = "public"
                is_public = true
                zip_first = false
                file_patterns = ["**/optional.txt"]
                if_clause = 'ENV_VAR_FOO == "foo"'
            """)
        )

        curdir = os.getcwd()
        os.chdir(tmp_path)
        _refresh_ci_settings()

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

        # remove all objects in both buckets before test
        for bucket in ['private', 'public']:
            for obj in client.list_objects(bucket, recursive=True):
                try:
                    client.remove_object(bucket, obj.object_name)
                except minio.error.S3Error as e:
                    logging.error(f'Error removing object: {e}')

        return client

    def test_all_without_optional(self, runner, s3_client, sample_artifacts_dir):
        commit_sha = 'cli_test_sha_123'

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
            ],
        )
        assert result.exit_code == 0

        objs = list(s3_client.list_objects('private', recursive=True))
        assert len(objs) == 3
        assert sorted(obj.object_name for obj in objs) == [
            f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/debug.zip',
            f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/flash.zip',
            f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/size.json',
        ]

        shutil.rmtree(sample_artifacts_dir)

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
            ],
        )
        assert result.exit_code == 0

        assert sorted(os.listdir(sample_artifacts_dir)) == [
            'build.log',
            'size.json',
            'test.bin',
        ]

        # test single artifact type download
        shutil.rmtree(sample_artifacts_dir)

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'flash',
            ],
        )
        assert result.exit_code == 0
        assert sorted(os.listdir(sample_artifacts_dir)) == [
            'test.bin',
        ]

    def test_all_with_optional(self, runner, s3_client, sample_artifacts_dir, tmp_path, monkeypatch):
        commit_sha = 'cli_test_sha_123'

        monkeypatch.setenv('ENV_VAR_FOO', 'foo')

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
            ],
        )
        assert result.exit_code == 0
        private_objs = list(s3_client.list_objects('private', recursive=True))
        public_objs = list(s3_client.list_objects('public', recursive=True))

        assert len(private_objs) == 3
        assert sorted(obj.object_name for obj in private_objs) == [
            f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/debug.zip',
            f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/flash.zip',
            f'espressif/esp-idf/{commit_sha}/app/build_esp32_build/size.json',
        ]

        assert len(public_objs) == 1
        assert public_objs[0].object_name == f'espressif/esp-idf/{commit_sha}/optional.txt'

        shutil.rmtree(sample_artifacts_dir)
        (tmp_path / 'optional.txt').unlink(missing_ok=True)

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
            ],
        )
        assert result.exit_code == 0
        assert sorted(os.listdir(sample_artifacts_dir)) == [
            'build.log',
            'size.json',
            'test.bin',
        ]
        assert (tmp_path / 'optional.txt').exists()

    def test_cli_generate_presigned_json(self, runner):
        commit_sha = 'cli_test_sha_123'

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'metrics',
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'generate-presigned-json',
                '--commit-sha',
                commit_sha,
                '--type',
                'metrics',
            ],
        )
        assert result.exit_code == 0

        presigned_urls = json.loads(result.stdout)
        assert sorted(presigned_urls.keys()) == ['app/build_esp32_build/size.json']

        response = requests.get(presigned_urls['app/build_esp32_build/size.json'])
        assert response.status_code == 200

    def test_cli_download_with_presigned_json(self, runner, tmp_path, sample_artifacts_dir):
        commit_sha = 'presigned_test_sha_123'

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

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'upload-artifacts',
                '--commit-sha',
                commit_sha,
                '--type',
                'metrics',
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'generate-presigned-json',
                '--commit-sha',
                commit_sha,
                '-o',
                str(tmp_path / 'presigned.json'),
            ],
        )
        assert result.exit_code == 0

        assert (tmp_path / 'presigned.json').exists()
        with open('presigned.json') as fr:
            assert sorted(json.load(fr).keys()) == [
                'app/build_esp32_build/flash.zip',
                'app/build_esp32_build/size.json',
            ]

        shutil.rmtree(sample_artifacts_dir, ignore_errors=True)

        result = runner.invoke(
            click_cli,
            [
                'gitlab',
                'download-artifacts',
                '--commit-sha',
                commit_sha,
                '--presigned-json',
                str(tmp_path / 'presigned.json'),
            ],
        )
        assert result.exit_code == 0

        # Verify the file was downloaded and extracted
        assert (sample_artifacts_dir / 'test.bin').exists()
        assert (sample_artifacts_dir / 'test.bin').read_text() == 'Binary content'
        assert (sample_artifacts_dir / 'size.json').exists()
        assert (sample_artifacts_dir / 'size.json').read_text() == '{"size": 1024}'

    # Error Handling Tests
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
        assert 'S3 client is not configured properly' in result.exception.args[0]

    def test_upload_without_s3_credentials(
        self,
        runner,
        tmp_path,
        sample_artifacts_dir,  # noqa
        monkeypatch,
    ):
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
        assert 'Configure S3 storage to upload artifacts' in result.exception.args[0]
