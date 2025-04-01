# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import click

from idf_ci.idf_gitlab import dynamic_pipeline_variables as dynamic_pipeline_variables_func
from idf_ci.idf_gitlab.api import ArtifactManager


@click.group()
def gitlab():
    """Group of idf_gitlab related commands"""
    pass


@gitlab.command()
def dynamic_pipeline_variables():
    """Output dynamic pipeline variables"""
    for k, v in dynamic_pipeline_variables_func().items():
        click.echo(f'{k}="{v}"')


@gitlab.command()
@click.option(
    '--type',
    'artifact_type',
    type=click.Choice(['debug', 'flash', 'metrics']),
    help='Type of artifacts to download. If not specified, downloads all types.',
)
@click.option('--commit-sha', help='Commit SHA to download artifacts from.')
@click.option('--branch', help='Git branch to get the latest pipeline from.')
@click.argument('folder', required=False)
def download_artifacts(artifact_type, commit_sha, branch, folder):
    """Download artifacts from a GitLab pipeline.

    This command downloads artifacts from either GitLab's built-in storage or S3
    storage, depending on the configuration. The artifacts are downloaded to the
    specified folder (or current directory if not specified).
    """
    manager = ArtifactManager()
    manager.download_artifacts(
        commit_sha=commit_sha,
        branch=branch,
        artifact_type=artifact_type,
        folder=folder,
    )


@gitlab.command()
@click.option(
    '--type',
    'artifact_type',
    type=click.Choice(['debug', 'flash', 'metrics']),
    help='Type of artifacts to upload',
)
@click.option(
    '--commit-sha',
    required=True,
    help='Commit SHA to upload artifacts to. Required for S3 storage.',
)
@click.argument('folder', required=False)
def upload_artifacts(artifact_type, commit_sha, folder):
    """Upload artifacts to S3 storage.

    This command uploads artifacts to S3 storage only. GitLab's built-in storage is not
    supported. The commit SHA is required to identify where to store the artifacts.

    :param commit_sha: Commit SHA to upload artifacts to
    :param artifact_type: Type of artifacts to upload (debug, flash, metrics)
    :param folder: Directory containing artifacts to upload
    """
    manager = ArtifactManager()
    manager.upload_artifacts(
        commit_sha=commit_sha,
        artifact_type=artifact_type,
        folder=folder,
    )
