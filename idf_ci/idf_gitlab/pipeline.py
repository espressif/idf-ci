# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
"""This file is used for generating the child pipeline for build jobs."""

import logging
import os
import re
import typing as t
from contextlib import contextmanager

import yaml
from idf_build_apps import App
from idf_build_apps.args import FindArguments
from jinja2 import Environment

from idf_ci.envs import get_env_vars
from idf_ci.idf_pytest import GroupedPytestCases, get_pytest_cases
from idf_ci.scripts import get_all_apps
from idf_ci.settings import IDF_CI_DEFAULT_TOOLCHAIN, CiSettings, get_ci_settings, suffix_filename, toolchain_filename

logger = logging.getLogger(__name__)


@contextmanager
def set_env(key: str, value: str) -> t.Iterator[None]:
    original = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if original is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original


def _parallel_count(item_count: int, runs_per_job: int) -> int:
    if item_count <= 0:
        return 0

    return (item_count - 1) // runs_per_job + 1


def _yaml_flow(value: t.Any) -> str:
    dumped = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True).strip()
    if dumped.endswith('...'):
        dumped = dumped[:-3].strip()
    return dumped


def _extra_variables_for_job(
    settings: CiSettings,
    job: t.Dict[str, t.Any],
    env: Environment,
) -> t.Dict[str, str]:
    fragment = settings.gitlab.test_pipeline.job_variables_jinja
    if not fragment.strip():
        return {}

    rendered = env.from_string(fragment).render(settings=settings, job=job).strip()
    if not rendered:
        return {}

    try:
        parsed = yaml.safe_load(rendered)
    except yaml.YAMLError as e:
        raise ValueError(f'gitlab.test_pipeline.job_variables_jinja rendered invalid YAML: {e}') from e

    if not isinstance(parsed, dict):
        raise ValueError(
            'gitlab.test_pipeline.job_variables_jinja must render to a YAML mapping of job variables, '
            f'got {type(parsed).__name__}'
        )

    return {_yaml_flow(key): _yaml_flow(value) for key, value in parsed.items()}


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
    settings = get_ci_settings()
    envs = get_env_vars()

    if compare_manifest_sha_filepath and not os.path.isfile(compare_manifest_sha_filepath):
        compare_manifest_sha_filepath = None

    if yaml_output is None:
        yaml_output = settings.gitlab.build_pipeline.yaml_filename

    for toolchain in settings.gitlab.build_enabled_toolchains:
        # Manifest conditions are evaluated during discovery, not at build time.
        with set_env('IDF_TOOLCHAIN', toolchain):
            if envs.select_by_filter_expr:
                test_related_apps, _ = get_all_apps(
                    paths=paths, marker_expr='not host_test', filter_expr=envs.select_by_filter_expr
                )
                non_test_related_apps: t.List[App] = []
            else:
                test_related_apps, non_test_related_apps = get_all_apps(
                    paths=paths,
                    modified_files=modified_files,
                    marker_expr='not host_test',
                    compare_manifest_sha_filepath=compare_manifest_sha_filepath,
                )

        app_list_suffix = envs.IDF_CI_ARTIFACT_NAMESPACE or ('' if toolchain == IDF_CI_DEFAULT_TOOLCHAIN else toolchain)
        dump_apps_to_txt(
            test_related_apps,
            suffix_filename(settings.collected_test_related_apps_filepath, app_list_suffix),
        )
        dump_apps_to_txt(
            non_test_related_apps,
            suffix_filename(settings.collected_non_test_related_apps_filepath, app_list_suffix),
        )

        output = toolchain_filename(yaml_output, toolchain)
        if not test_related_apps and not non_test_related_apps:
            logger.info('No apps found for %s, generating fake_pass job', toolchain)
            with open(output, 'w') as fw:
                yaml.safe_dump(_get_fake_pass_job(settings, settings.gitlab.build_pipeline.workflow_name), fw)
            continue

        logger.info(
            'Toolchain %s: %d test related apps, %d non-test related apps',
            toolchain,
            len(test_related_apps),
            len(non_test_related_apps),
        )
        environment = Environment()
        with open(output, 'w') as fw:
            fw.write(
                environment.from_string(settings.gitlab.build_pipeline.yaml_jinja).render(
                    job_template=environment.from_string(settings.gitlab.build_pipeline.job_template_jinja).render(
                        settings=settings,
                        toolchain=toolchain,
                    ),
                    jobs=environment.from_string(settings.gitlab.build_pipeline.jobs_jinja).render(
                        settings=settings,
                        toolchain=toolchain,
                        test_related_apps_count=len(test_related_apps),
                        test_related_parallel_count=_parallel_count(
                            len(test_related_apps), settings.gitlab.build_pipeline.runs_per_job
                        ),
                        non_test_related_apps_count=len(non_test_related_apps),
                        non_test_related_parallel_count=_parallel_count(
                            len(non_test_related_apps), settings.gitlab.build_pipeline.runs_per_job
                        ),
                    ),
                    settings=settings,
                    toolchain=toolchain,
                    default_toolchain=IDF_CI_DEFAULT_TOOLCHAIN,
                    test_yaml_filename=toolchain_filename(settings.gitlab.test_pipeline.yaml_filename, toolchain),
                    generate_tests=toolchain in settings.gitlab.test_enabled_toolchains,
                    test_related_apps_count=len(test_related_apps),
                )
            )
        logger.info('Build child pipeline generated successfully in %s', output)


def test_child_pipeline(
    yaml_output: t.Optional[str] = None,
    *,
    cases: t.Optional[GroupedPytestCases] = None,
    toolchain: str = IDF_CI_DEFAULT_TOOLCHAIN,
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

    if not re.fullmatch(r'[A-Za-z0-9_-]+', toolchain):
        raise ValueError('toolchain must be a nonempty filename-safe name')

    if yaml_output is None:
        yaml_output = toolchain_filename(settings.gitlab.test_pipeline.yaml_filename, toolchain)

    if set(settings.gitlab.test_pipeline.skip_mr_labels) & {
        label.strip() for label in (get_env_vars().CI_MERGE_REQUEST_LABELS or '').split(',')
    }:
        logger.info('Skipping target tests because a configured MR label is present')
        cases = GroupedPytestCases([])
    elif cases is None:
        with set_env('IDF_TOOLCHAIN', toolchain):
            if get_env_vars().IDF_CI_APPLY_BUILD_TEST_RULES_TO_PYTEST:
                # Pytest collection does not load idf-build-apps manifests. Load the
                # same rules as app discovery before deciding which cases can run.
                previous_manifest = App.MANIFEST
                try:
                    manifest_args = FindArguments()
                    manifest = App.MANIFEST if manifest_args.manifest_files else None
                    cases = GroupedPytestCases(
                        [
                            case
                            for case in get_pytest_cases()
                            if manifest is None
                            or all(
                                app.target in manifest.enable_test_targets(app.path, config_name=app.config)
                                for app in case.apps
                            )
                        ]
                    )
                finally:
                    App.MANIFEST = previous_manifest
            else:
                cases = GroupedPytestCases(get_pytest_cases())

    envs = get_env_vars()
    exact_exclusions = set()
    wildcard_exclusions = []
    for rule in settings.gitlab.test_pipeline.exclude_runner_tags + (
        (envs.EXCLUDE_RUNNER_TAGS or '').split(';') if envs.EXCLUDE_RUNNER_TAGS else []
    ):
        tags = [tag.strip() for tag in rule.split(',')]
        if (
            not all(tags)
            or any('*' in tag and tag != '*' for tag in tags)
            or ('*' in tags and (tags[-1] != '*' or len(tags) < 2 or tags.count('*') != 1))
        ):
            raise ValueError(f'Invalid runner-tag exclusion: {rule!r}')
        if tags[-1] == '*':
            wildcard_exclusions.append(frozenset(tags[:-1]))
        else:
            exact_exclusions.add(frozenset(tags))

    if exact_exclusions or wildcard_exclusions:
        excluded_keys = {
            key
            for key in cases.grouped_cases
            if frozenset(key.runner_tags) in exact_exclusions
            or any(tags <= frozenset(key.runner_tags) for tags in wildcard_exclusions)
        }
        for key in excluded_keys:
            logger.warning('Excluding test cases with runner tags: %s', key.runner_tags)
        cases = GroupedPytestCases(
            [case for key, grouped in cases.grouped_cases.items() if key not in excluded_keys for case in grouped],
            additional_dict=cases.additional_dict,
        )

    if not cases.grouped_cases:
        logger.info('No test cases found, generating fake_pass job to skip the entire test child pipeline')
        with open(yaml_output, 'w') as fw:
            yaml.safe_dump(_get_fake_pass_job(settings, settings.gitlab.test_pipeline.workflow_name), fw)
        return

    env = Environment()
    jobs = []
    for key, grouped_cases in cases.grouped_cases.items():
        job = {
            'name': f'{key.target_selector} - {key.env_selector}',
            'tags': sorted(key.runner_tags),
            # quote nodeids to avoid special chars issues
            'nodes': '"' + ' '.join([f"'{c.item.nodeid}'" for c in grouped_cases]) + '"',
            'parallel_count': _parallel_count(
                len(grouped_cases),
                settings.gitlab.test_pipeline.runs_per_job,
            ),
            **cases.additional_dict.get(key, {}),
        }
        job['extra_extends'] = list(
            dict.fromkeys(
                job.get('extra_extends', [])
                + [
                    template
                    for marker in key.env_selector.split(',')
                    for template in settings.gitlab.test_pipeline.extra_extends_by_env_marker.get(marker, [])
                ]
            )
        )
        job['extra_variables'] = _extra_variables_for_job(settings, job, env)
        if envs.IDF_CI_ARTIFACT_NAMESPACE:
            job['extra_variables']['IDF_CI_ARTIFACT_NAMESPACE'] = _yaml_flow(envs.IDF_CI_ARTIFACT_NAMESPACE)
        jobs.append(job)

    extra_jobs = env.from_string(settings.gitlab.test_pipeline.extra_jobs_jinja).render(
        settings=settings,
        jobs=jobs,
    )
    job_template = env.from_string(settings.gitlab.test_pipeline.job_template_jinja)
    jobs_template = env.from_string(settings.gitlab.test_pipeline.jobs_jinja)
    yaml_template = env.from_string(settings.gitlab.test_pipeline.yaml_jinja)

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
                extra_jobs=extra_jobs,
                settings=settings,
                toolchain=toolchain,
                default_toolchain=IDF_CI_DEFAULT_TOOLCHAIN,
            )
        )

    logger.info('Test child pipeline generated successfully in %s', yaml_output)
