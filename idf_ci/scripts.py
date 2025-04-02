# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import fnmatch
import logging
import os
import typing as t

from idf_build_apps import App, build_apps, find_apps
from idf_build_apps.constants import SUPPORTED_TARGETS, BuildStatus

from . import get_pytest_cases
from ._compat import UNDEF, UndefinedOr, is_defined_and_satisfies, is_undefined
from .idf_gitlab.envs import GitlabEnvVars
from .settings import CiSettings

logger = logging.getLogger(__name__)


def preprocess_args(
    modified_files: t.Optional[t.List[str]] = None,
    modified_components: t.Optional[t.List[str]] = None,
    filter_expr: UndefinedOr[t.Optional[str]] = UNDEF,
    default_build_targets: UndefinedOr[t.List[str]] = UNDEF,
) -> t.Tuple[
    t.Optional[t.List[str]],
    t.Optional[t.List[str]],
    t.Optional[str],
    t.List[str],
    t.Optional[t.List[App]],
    t.Optional[t.List[App]],
]:
    """Set values according to the environment variables, .toml settings, and defaults."""
    env = GitlabEnvVars()
    settings = CiSettings()

    # `default_build_targets`, args > env vars, append settings `extra_default_build_targets`
    if is_undefined(default_build_targets):
        default_build_targets = SUPPORTED_TARGETS

    if is_defined_and_satisfies(settings.extra_default_build_targets):
        default_build_targets = [*default_build_targets, *settings.extra_default_build_targets]  # type: ignore

    # build and run all pytest cases
    if env.select_all_pytest_cases:
        return None, None, None, default_build_targets  # type: ignore

    # `modified_files`, args > env vars
    if modified_files is None and is_defined_and_satisfies(env.CHANGED_FILES_SEMICOLON_SEPARATED):
        modified_files = env.CHANGED_FILES_SEMICOLON_SEPARATED.split(';')  # type: ignore

    # `modified_components`, args > settings
    if modified_files is not None and modified_components is None:
        modified_components = sorted(settings.get_modified_components(modified_files))

    # `filter_expr`, args > env vars
    if is_undefined(filter_expr):
        filter_expr = env.IDF_CI_SELECT_BY_FILTER_EXPR

    if is_defined_and_satisfies(filter_expr):
        logger.info(
            'Running with quick test filter: %s. Skipping dependency-driven build. Build and test only filtered cases.',
            filter_expr,
        )
        modified_files = None
        modified_components = None

    # `test_related_apps`, settings
    test_related_apps, non_test_related_apps = settings.get_collected_apps_list()

    return (  # type: ignore
        modified_files,
        modified_components,
        filter_expr,
        default_build_targets,
        test_related_apps,
        non_test_related_apps,
    )


def get_all_apps(
    *,
    paths: t.Optional[t.List[str]] = None,
    target: str = 'all',
    # args that may be set by env vars or .idf_ci.toml
    modified_files: t.Optional[t.List[str]] = None,
    modified_components: t.Optional[t.List[str]] = None,
    filter_expr: UndefinedOr[t.Optional[str]] = UNDEF,
    default_build_targets: UndefinedOr[t.List[str]] = UNDEF,
    # args that may be set by target
    marker_expr: UndefinedOr[t.Optional[str]] = UNDEF,
    # additional args
    compare_manifest_sha_filepath: t.Optional[str] = None,
) -> t.Tuple[t.List[App], t.List[App]]:
    """Get test-related and non-test-related applications.

    :param paths: List of paths to search for applications
    :param target: Target device(s) separated by commas
    :param modified_files: List of modified files
    :param modified_components: List of modified components
    :param filter_expr: Pytest filter expression -k
    :param default_build_targets: Default build targets to use
    :param marker_expr: Pytest marker expression -m
    :param compare_manifest_sha_filepath: Path to the manifest SHA file generated by
        `idf-build-apps dump-manifest-sha`

    :returns: Tuple of (test_related_apps, non_test_related_apps)
    """
    (
        modified_files,
        modified_components,
        filter_expr,
        default_build_targets,
        test_related_apps,
        non_test_related_apps,
    ) = preprocess_args(
        modified_files=modified_files,
        modified_components=modified_components,
        filter_expr=filter_expr,
        default_build_targets=default_build_targets,
    )

    if test_related_apps is not None and non_test_related_apps is not None:
        return test_related_apps, non_test_related_apps

    paths = paths or ['.']

    apps = []
    for _t in target.split(','):
        if _t != 'all' and _t not in default_build_targets:
            default_build_targets = [*default_build_targets, _t]

        apps.extend(
            find_apps(
                paths,
                _t,
                modified_files=modified_files,
                modified_components=modified_components,
                include_skipped_apps=True,
                default_build_targets=default_build_targets,
                compare_manifest_sha_filepath=compare_manifest_sha_filepath,
            )
        )

    cases = get_pytest_cases(paths=paths, target=target, marker_expr=marker_expr, filter_expr=filter_expr)
    if not cases:
        return [], sorted(apps)

    # Get modified pytest cases if any
    modified_pytest_cases = []
    if modified_files:
        modified_pytest_scripts = [
            os.path.dirname(f) for f in modified_files if fnmatch.fnmatch(os.path.basename(f), 'test_*.py')
        ]
        if modified_pytest_scripts:
            modified_pytest_cases = get_pytest_cases(
                paths=modified_pytest_scripts,
                target=target,
                marker_expr=marker_expr,
                filter_expr=filter_expr,
            )

    # Create dictionaries mapping app info to test cases
    def get_app_dict(_cases):
        return {(case_app.path, case_app.target, case_app.config): _case for _case in _cases for case_app in _case.apps}

    pytest_dict = get_app_dict(cases)
    modified_pytest_dict = get_app_dict(modified_pytest_cases)

    test_apps = set()
    non_test_apps = set()

    for app in apps:
        app_key = (os.path.abspath(app.app_dir), app.target, app.config_name or 'default')
        # override build_status if test script got modified
        case = modified_pytest_dict.get(app_key)
        if case:
            test_apps.add(app)
            app.build_status = BuildStatus.SHOULD_BE_BUILT
            logger.debug('Found app: %s - required by modified test case %s', app, case.path)
        elif app.build_status != BuildStatus.SKIPPED:
            case = pytest_dict.get(app_key)
            if case:
                test_apps.add(app)
                # build or not should be decided by the build stage
                logger.debug('Found test-related app: %s - required by %s', app, case.path)
            else:
                non_test_apps.add(app)
                logger.debug('Found non-test-related app: %s', app)

    return sorted(test_apps), sorted(non_test_apps)


def build(
    *,
    paths: t.Optional[t.List[str]] = None,
    target: str = 'all',
    parallel_count: int = 1,
    parallel_index: int = 1,
    modified_files: t.Optional[t.List[str]] = None,
    modified_components: t.Optional[t.List[str]] = None,
    only_test_related: bool = False,
    only_non_test_related: bool = False,
    dry_run: bool = False,
    verbose: t.Optional[int] = None,
    marker_expr: UndefinedOr[str] = UNDEF,
    filter_expr: UndefinedOr[str] = UNDEF,
) -> t.Tuple[t.List[App], int]:
    """Build applications based on specified parameters.

    :param paths: List of paths to search for applications
    :param target: Target device(s) separated by commas
    :param parallel_count: Total number of parallel jobs
    :param parallel_index: Index of current parallel job (1-based)
    :param modified_files: List of modified files
    :param modified_components: List of modified components
    :param only_test_related: Only build test-related applications
    :param only_non_test_related: Only build non-test-related applications
    :param dry_run: Do not actually build, just simulate
    :param verbose: Verbosity level
    :param marker_expr: Pytest marker expression
    :param filter_expr: Filter expression

    :returns: Tuple of (built apps, build return code)
    """
    # call it here again for a future usage in `build_apps`
    _, modified_components, _, _, _, _ = preprocess_args(
        modified_files=modified_files,
        modified_components=modified_components,
    )

    test_related_apps, non_test_related_apps = get_all_apps(
        paths=paths,
        target=target,
        modified_files=modified_files,
        modified_components=modified_components,
        marker_expr=marker_expr,
        filter_expr=filter_expr,
    )

    for app in test_related_apps:
        app.preserve = CiSettings().preserve_test_related_apps

    for app in non_test_related_apps:
        app.preserve = CiSettings().preserve_non_test_related_apps

    if not only_test_related and not only_non_test_related:
        apps = sorted([*test_related_apps, *non_test_related_apps])
    elif only_test_related:
        apps = test_related_apps
    else:
        apps = non_test_related_apps

    ret = build_apps(
        apps,
        parallel_count=parallel_count,
        parallel_index=parallel_index,
        dry_run=dry_run,
        modified_files=modified_files,
        modified_components=modified_components,
        verbose=verbose,
    )
    return apps, ret
