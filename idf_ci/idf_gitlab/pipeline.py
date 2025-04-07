# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
"""This file is used for generating the child pipeline for build jobs."""

import logging
import os
import typing as t

from idf_build_apps import App
from jinja2 import Environment

from idf_ci.idf_gitlab.envs import GitlabEnvVars
from idf_ci.scripts import get_all_apps
from idf_ci.settings import CiSettings

logger = logging.getLogger(__name__)


def dump_apps_to_txt(apps: t.List[App], output_file: str) -> None:
    """Dump a list of apps to a text file, one app per line."""
    with open(output_file, 'w') as fw:
        for app in apps:
            fw.write(app.model_dump_json() + '\n')


def build_child_pipeline(
    paths: t.Optional[t.List[str]] = None,
    modified_files: t.Optional[t.List[str]] = None,
    compare_manifest_sha_filepath: t.Optional[str] = None,
    yaml_output: t.Optional[str] = None,
) -> None:
    """Generate build child pipeline."""
    envs = GitlabEnvVars()
    settings = CiSettings()

    if compare_manifest_sha_filepath and not os.path.isfile(compare_manifest_sha_filepath):
        compare_manifest_sha_filepath = None

    if yaml_output is None:
        yaml_output = settings.gitlab.build_child_pipeline_yaml_filename

    # Check if we should run quick pipeline
    test_related_apps: t.List[App] = []
    non_test_related_apps: t.List[App] = []
    if envs.select_by_filter_expr:
        # we only build test related apps
        test_related_apps, _ = get_all_apps(
            paths=paths,
            marker_expr='not host_test',
            filter_expr=envs.select_by_filter_expr,
        )
        dump_apps_to_txt(test_related_apps, settings.collected_test_related_apps_filepath)
    else:
        test_related_apps, non_test_related_apps = get_all_apps(
            paths=paths,
            modified_files=modified_files,
            marker_expr='not host_test',
            compare_manifest_sha_filepath=compare_manifest_sha_filepath,
        )
        dump_apps_to_txt(test_related_apps, settings.collected_test_related_apps_filepath)
        dump_apps_to_txt(non_test_related_apps, settings.collected_non_test_related_apps_filepath)

    apps_total = len(test_related_apps) + len(non_test_related_apps)
    parallel_count = apps_total // settings.gitlab.build_apps_count_per_job + 1

    logger.info(
        'Found %d apps, %d test related apps, %d non-test related apps',
        apps_total,
        len(test_related_apps),
        len(non_test_related_apps),
    )
    logger.info('Parallel count: %d', parallel_count)

    build_jobs_template = Environment().from_string(settings.gitlab.build_jobs_jinja_template)
    generate_test_child_pipeline_template = Environment().from_string(
        settings.gitlab.generate_test_child_pipeline_job_jinja_template
    )
    build_child_pipeline_template = Environment().from_string(settings.gitlab.build_child_pipeline_yaml_jinja_template)

    with open(yaml_output, 'w') as fw:
        fw.write(
            build_child_pipeline_template.render(
                build_jobs_yaml=build_jobs_template.render(
                    parallel_count=parallel_count,
                ),
                generate_test_child_pipeline_yaml=generate_test_child_pipeline_template.render(
                    test_child_pipeline_yaml_filename=settings.gitlab.test_child_pipeline_yaml_filename,
                ),
            )
        )
