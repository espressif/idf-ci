# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
"""This file is used for generating the child pipeline for build jobs."""

import logging
import os
import typing as t

import yaml
from idf_build_apps import App
from jinja2 import Environment

from idf_ci.envs import GitlabEnvVars
from idf_ci.idf_pytest import GroupedPytestCases, get_pytest_cases
from idf_ci.scripts import get_all_apps
from idf_ci.settings import CiSettings, get_ci_settings

logger = logging.getLogger(__name__)


def _get_fake_pass_job(settings: CiSettings, workflow_name: str) -> t.Dict[str, t.Any]:
    # no matter being used in build or test child pipeline,
    # always use the same fake_pass job that extends the build job template
    # since test child pipeline tags are generated programmatically
    return {
        'fake_pass': {
            'stage': settings.gitlab.build_pipeline.job_stage,
            'tags': settings.gitlab.build_pipeline.job_tags,
            'before_script': [],
            'after_script': [],
            'cache': [],
            'needs': [],
            'script': [
                'echo "skip the entire child pipeline"',
            ],
        },
        # required for GitLab to recognize this as a valid pipeline
        'workflow': {
            'name': workflow_name,  # different workflow names for build and test child pipelines
            'rules': [
                {'when': 'always'},
            ],
        },
    }


def dump_apps_to_txt(apps: t.List[App], output_file: str) -> None:
    """Dump a list of apps to a text file, one app per line."""
    with open(output_file, 'w') as fw:
        for app in apps:
            fw.write(app.model_dump_json() + '\n')


def build_child_pipeline(
    *,
    paths: t.Optional[t.List[str]] = None,
    modified_files: t.Optional[t.List[str]] = None,
    compare_manifest_sha_filepath: t.Optional[str] = None,
    yaml_output: t.Optional[str] = None,
) -> None:
    """Generate build child pipeline."""
    envs = GitlabEnvVars()
    settings = get_ci_settings()

    if compare_manifest_sha_filepath and not os.path.isfile(compare_manifest_sha_filepath):
        compare_manifest_sha_filepath = None

    if yaml_output is None:
        yaml_output = settings.gitlab.build_pipeline.yaml_filename

    # Check if we should run quick pipeline
    if envs.select_by_filter_expr:
        # we only build test related apps
        test_related_apps, _ = get_all_apps(
            paths=paths,
            marker_expr='not host_test',
            filter_expr=envs.select_by_filter_expr,
        )
        non_test_related_apps: t.List[App] = []
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
    test_related_parallel_count = (
        len(test_related_apps) // settings.gitlab.build_pipeline.runs_per_job + 1 if test_related_apps else 0
    )
    non_test_related_parallel_count = (
        len(non_test_related_apps) // settings.gitlab.build_pipeline.runs_per_job + 1 if non_test_related_apps else 0
    )

    if not apps_total:
        logger.info('No apps found, generating fake_pass job to skip the entire build child pipeline')
        with open(yaml_output, 'w') as fw:
            yaml.safe_dump(_get_fake_pass_job(settings, settings.gitlab.build_pipeline.workflow_name), fw)
            return

    logger.info(
        'Found %d apps, %d test related apps, %d non-test related apps',
        apps_total,
        len(test_related_apps),
        len(non_test_related_apps),
    )
    logger.info(
        'Test related parallel count: %d, Non-test related parallel count: %d',
        test_related_parallel_count,
        non_test_related_parallel_count,
    )

    job_template = Environment().from_string(settings.gitlab.build_pipeline.job_template_jinja)
    jobs_template = Environment().from_string(settings.gitlab.build_pipeline.jobs_jinja)
    yaml_template = Environment().from_string(settings.gitlab.build_pipeline.yaml_jinja)

    with open(yaml_output, 'w') as fw:
        fw.write(
            yaml_template.render(
                job_template=job_template.render(
                    settings=settings,
                ),
                jobs=jobs_template.render(
                    settings=settings,
                    test_related_apps_count=len(test_related_apps),
                    test_related_parallel_count=test_related_parallel_count,
                    non_test_related_apps_count=len(non_test_related_apps),
                    non_test_related_parallel_count=non_test_related_parallel_count,
                ),
                settings=settings,
                test_related_apps_count=len(test_related_apps),
            )
        )

    logger.info('Build child pipeline generated successfully in %s', yaml_output)


def test_child_pipeline(
    yaml_output: str,
    *,
    cases: t.Optional[GroupedPytestCases] = None,
) -> None:
    """This function is used to generate the child pipeline for test jobs.

    Suppose the ci_build_artifacts_filepatterns is downloaded already

    .. note::

        parallel:matrix does not support array as value, we generate all jobs here

    .. warning::

        temp workaround: ``eval pytest $nodes`` required.

        if define nodes like ``"tests/test_example.py::test_example[param1 param2]
        tests/test_another.py::test_another[param1 param2]"`` and call ``pytest
        $nodes``, will raise error: ``ERROR: file or directory not found: param2]``

        if define nodes like ``"'tests/test_example.py::test_example[param1 param2]'
        'tests/test_another.py::test_another[param1 param2]'"``, and call ``pytest
        $nodes``, will raise error: ``ERROR: file or directory not found:
        'tests/test_example.py::test_example[param1``

        Each node has to be single quoted, otherwise special chars or whitespaces in
        nodeid may cause issues. It seems like ``eval pytest $nodes`` with nodes defined
        as ``"'nodeid1' 'nodeid2'"`` is the only way to make it work.

    Example output:

    .. code-block:: yaml

        .default_test_settings:
            script:
                - eval pytest $nodes

        esp32 - generic:
            extends:
                - .default_test_settings
            tags:
                - esp32
                - generic
            variables:
                nodes: "'nodeid1' 'nodeid2'"
    """
    settings = get_ci_settings()

    if yaml_output is None:
        yaml_output = settings.gitlab.test_pipeline.yaml_filename

    if cases is None:
        cases = GroupedPytestCases(get_pytest_cases())

    if not cases.grouped_cases:
        logger.info('No test cases found, generating fake_pass job to skip the entire test child pipeline')
        with open(yaml_output, 'w') as fw:
            yaml.safe_dump(_get_fake_pass_job(settings, settings.gitlab.test_pipeline.workflow_name), fw)
        return

    jobs = []
    for key, grouped_cases in cases.grouped_cases.items():
        jobs.append(
            {
                'name': f'{key.target_selector} - {key.env_selector}',
                'tags': sorted(key.runner_tags),
                # quote nodeids to avoid special chars issues
                'nodes': '"' + ' '.join([f"'{c.item.nodeid}'" for c in grouped_cases]) + '"',
                'parallel_count': len(grouped_cases) // settings.gitlab.test_pipeline.runs_per_job + 1,
                **cases.additional_dict.get(key, {}),
            }
        )

    job_template = Environment().from_string(settings.gitlab.test_pipeline.job_template_jinja)
    jobs_template = Environment().from_string(settings.gitlab.test_pipeline.jobs_jinja)
    yaml_template = Environment().from_string(settings.gitlab.test_pipeline.yaml_jinja)

    with open(yaml_output, 'w') as fw:
        fw.write(
            yaml_template.render(
                default_template=job_template.render(
                    settings=settings,
                ),
                jobs=jobs_template.render(
                    jobs=jobs,
                    settings=settings,
                ),
                settings=settings,
            )
        )

    logger.info('Test child pipeline generated successfully in %s', yaml_output)
