# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import subprocess
import tempfile

import pytest

from idf_ci.idf_gitlab import ArtifactParams


@pytest.fixture(autouse=True)
def setup(tmp_path):
    """Change to temporary directory for tests."""
    curdir = os.getcwd()
    os.chdir(tmp_path)

    yield

    os.chdir(curdir)


@pytest.fixture(autouse=True)
def setup_git_repo(tmp_path):
    """Set up a git repository with initial commit and optional branch."""
    # Create a git repo
    subprocess.run(['git', 'init'], check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], check=True)

    # Create initial commit on feature branch
    subprocess.run(['git', 'checkout', '-b', 'feature-branch'], check=True)
    (tmp_path / 'test.txt').write_text('test')
    subprocess.run(['git', 'add', 'test.txt'], check=True)
    subprocess.run(['git', 'commit', '-m', 'feature commit'], check=True)

    # Create local branch
    subprocess.run(['git', 'checkout', '-b', 'local-branch'], check=True)
    (tmp_path / 'local.txt').write_text('local content')
    subprocess.run(['git', 'add', 'local.txt'], check=True)
    subprocess.run(['git', 'commit', '-m', 'local commit'], check=True)

    return tmp_path


def get_commit_sha(ref='HEAD'):
    """Get commit SHA for a given reference."""
    return subprocess.run(
        ['git', 'rev-parse', ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def feature_sha():
    """Set up git repo with feature branch and return its SHA."""
    return get_commit_sha('feature-branch')


@pytest.fixture
def local_sha():
    """Set up git repo with local branch and return its SHA."""
    return get_commit_sha('local-branch')


def test_commit_sha_precedence(monkeypatch, feature_sha, local_sha):
    """Test the precedence of commit SHA resolution in StorageParams."""
    # 1. Test CLI commit SHA has the highest priority
    params = ArtifactParams(commit_sha='cli-sha')
    assert params.commit_sha == 'cli-sha'

    # 2. Test PIPELINE_COMMIT_SHA has second priority
    monkeypatch.setenv('PIPELINE_COMMIT_SHA', 'env-sha')
    params = ArtifactParams()
    assert params.commit_sha == 'env-sha'

    # 3. Test specified branch precedes local branch
    monkeypatch.delenv('PIPELINE_COMMIT_SHA')
    params = ArtifactParams(branch='feature-branch')
    assert params.commit_sha == feature_sha

    # 4. Test local branch latest commit
    params = ArtifactParams()
    assert params.commit_sha == local_sha

    # 5. Test ValueError when no commit SHA can be determined
    new_empty_folder = os.path.join(tempfile.gettempdir(), 'new_empty_folder')
    os.makedirs(new_empty_folder, exist_ok=True)
    os.chdir(new_empty_folder)

    with pytest.raises(
        ValueError,
        match='Failed to get commit SHA from git command. '
        'Must set commit_sha or branch parameter, or set PIPELINE_COMMIT_SHA env var',
    ):
        ArtifactParams()
