# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import fnmatch
import logging
import os
import typing as t

from idf_build_apps import App, build_apps, find_apps
from idf_build_apps.constants import SUPPORTED_TARGETS, BuildStatus

from . import get_pytest_cases
from ._compat import UNDEF, Undefined
from .settings import CiSettings

logger = logging.getLogger(__name__)


def get_all_apps(
    paths: t.List[str],
    target: str = 'all',
    *,
    modified_files: t.Optional[t.List[str]] = None,
    modified_components: t.Optional[t.List[str]] = None,
    marker_expr: str = UNDEF,
    default_build_targets: t.List[str] = UNDEF,  # type: ignore
) -> t.Tuple[t.Set[App], t.Set[App]]:
    apps = []
    for _t in target.split(','):
        if isinstance(default_build_targets, Undefined):
            if _t != 'all' and _t not in SUPPORTED_TARGETS:
                default_targets = list({*SUPPORTED_TARGETS, _t})
            else:
                default_targets = SUPPORTED_TARGETS
        else:
            default_targets = default_build_targets

        apps.extend(
            find_apps(
                paths,
                _t,
                modified_files=modified_files,
                modified_components=modified_components,
                include_skipped_apps=True,
                default_build_targets=default_targets,
            )
        )

    cases = get_pytest_cases(paths, target, marker_expr=marker_expr)
    if not cases:
        return set(), set(apps)

    # Get modified pytest cases if any
    modified_pytest_cases = []
    if modified_files:
        modified_pytest_scripts = [
            os.path.dirname(f) for f in modified_files if fnmatch.fnmatch(os.path.basename(f), 'test_*.py')
        ]
        if modified_pytest_scripts:
            modified_pytest_cases = get_pytest_cases(modified_pytest_scripts, target, marker_expr=marker_expr)

    # Create dictionaries mapping app info to test cases
    def get_app_dict(cases):
        return {(case_app.path, case_app.target, case_app.config): case for case in cases for case_app in case.apps}

    pytest_dict = get_app_dict(cases)
    modified_pytest_dict = get_app_dict(modified_pytest_cases)

    test_related_apps = set()
    non_test_related_apps = set()

    for app in apps:
        app_key = (os.path.abspath(app.app_dir), app.target, app.config_name or 'default')
        # override build_status if test script got modified\
        _case = modified_pytest_dict.get(app_key)
        if _case:
            test_related_apps.add(app)
            app.build_status = BuildStatus.SHOULD_BE_BUILT
            logger.debug('Found app: %s - required by modified test case %s', app, _case.path)
        elif app.build_status != BuildStatus.SKIPPED:
            _case = pytest_dict.get(app_key)
            if _case:
                test_related_apps.add(app)
                # build or not should be decided by the build stage
                logger.debug('Found test-related app: %s - required by %s', app, _case.path)
            else:
                non_test_related_apps.add(app)
                logger.debug('Found non-test-related app: %s', app)

    return test_related_apps, non_test_related_apps


def build(
    paths: t.List[str],
    target: str,
    *,
    parallel_count: int = 1,
    parallel_index: int = 1,
    modified_files: t.Optional[t.List[str]] = None,
    only_test_related: bool = False,
    only_non_test_related: bool = False,
    dry_run: bool = False,
    verbose: t.Optional[int] = None,
) -> t.Tuple[t.List[App], int]:
    modified_components = None
    if modified_files is not None:
        modified_components = sorted(CiSettings().get_modified_components(modified_files))
        logger.debug('Modified files: %s', modified_files)
        logger.debug('Modified components: %s', modified_components)

    # we have to call get_all_apps first, then call build_apps(apps)
    test_related_apps, non_test_related_apps = get_all_apps(
        paths,
        target,
        modified_files=modified_files,
        modified_components=modified_components,
    )

    for _app in test_related_apps:
        _app.preserve = CiSettings().preserve_test_related_apps

    for _app in non_test_related_apps:
        _app.preserve = CiSettings().preserve_non_test_related_apps

    if not only_test_related and not only_non_test_related:
        apps = sorted(test_related_apps.union(non_test_related_apps))
    elif only_test_related:
        apps = sorted(test_related_apps)
    else:
        apps = sorted(non_test_related_apps)

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
