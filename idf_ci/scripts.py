# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import fnmatch
import logging
import os
import subprocess
import typing as t

from idf_build_apps import App, build_apps, find_apps
from idf_build_apps.constants import SUPPORTED_TARGETS, BuildStatus

from . import get_pytest_cases
from ._compat import UNDEF, PathLike, Undefined
from .profiles import get_build_profile
from .settings import CiSettings

LOGGER = logging.getLogger(__name__)


def get_all_apps(
    paths: t.List[str],
    target: str = 'all',
    *,
    profiles: t.List[PathLike] = UNDEF,  # type: ignore
    modified_files: t.Optional[t.List[str]] = None,
    modified_components: t.Optional[t.List[str]] = None,
    marker_expr: str = UNDEF,
    default_build_targets: t.List[str] = UNDEF,  # type: ignore
) -> t.Tuple[t.Set[App], t.Set[App]]:
    build_profile = get_build_profile(profiles)

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
                config_file=build_profile.merged_profile_path,
                modified_files=modified_files,
                modified_components=modified_components,
                include_skipped_apps=True,
                default_build_targets=default_targets,
            )
        )

    cases = get_pytest_cases(paths, target, profiles=CiSettings().test_profiles, marker_expr=marker_expr)

    # Get modified pytest cases if any
    modified_pytest_cases = []
    if modified_files:
        modified_pytest_scripts = [
            os.path.dirname(f) for f in modified_files if fnmatch.fnmatch(os.path.basename(f), 'pytest_*.py')
        ]
        if modified_pytest_scripts:
            modified_pytest_cases = get_pytest_cases(
                modified_pytest_scripts, target, profiles=CiSettings().test_profiles, marker_expr=marker_expr
            )

    # Create dictionaries mapping app info to test cases
    def get_app_dict(cases):
        return {(case_app.path, case_app.target, case_app.config): case for case in cases for case_app in case.apps}

    pytest_dict = get_app_dict(cases)
    modified_pytest_dict = get_app_dict(modified_pytest_cases)

    test_related_apps = set()
    non_test_related_apps = set()

    for app in apps:
        app_key = (os.path.abspath(app.app_dir), app.target, app.config_name or 'default')
        # override build_status if test script got modified
        if _case := modified_pytest_dict.get(app_key):
            test_related_apps.add(app)
            app.build_status = BuildStatus.SHOULD_BE_BUILT
            LOGGER.debug('Found app: %s - required by modified test case %s', app, _case.path)
        elif app.build_status != BuildStatus.SKIPPED:
            if _case := pytest_dict.get(app_key):
                test_related_apps.add(app)
                # build or not should be decided by the build stage
                LOGGER.debug('Found test-related app: %s - required by %s', app, _case.path)
            else:
                non_test_related_apps.add(app)
                LOGGER.debug('Found non-test-related app: %s', app)

    print(f'Found {len(test_related_apps)} test-related apps')
    print(f'Found {len(non_test_related_apps)} non-test-related apps')

    return test_related_apps, non_test_related_apps


def build(
    paths: t.List[str],
    target: str,
    *,
    profiles: t.List[PathLike] = UNDEF,  # type: ignore
    parallel_count: int = 1,
    parallel_index: int = 1,
    modified_files: t.Optional[t.List[str]] = None,
    test_related: bool = False,
    non_test_related: bool = False,
    dry_run: bool = False,
):
    build_profile = get_build_profile(profiles)

    modified_components = None
    if modified_files is not None:
        modified_components = sorted(CiSettings().get_modified_components(modified_files))
        LOGGER.debug('Modified files: %s', modified_files)
        LOGGER.debug('Modified components: %s', modified_components)

    if test_related is False and non_test_related is False:
        # call idf-build-apps build directly
        args = [
            'idf-build-apps',
            'build',
            '-p',
            *paths,
            '-t',
            target,
            '--config-file',
            build_profile.merged_profile_path,
            '--parallel-count',
            str(parallel_count),
            '--parallel-index',
            str(parallel_index),
        ]

        if modified_files:
            args.extend(
                [
                    '--modified-files',
                    ';'.join(modified_files) if modified_files else ';',
                    '--modified-components',
                    ';'.join(modified_components) if modified_components else ';',
                ]
            )

        if dry_run:
            args.append('--dry-run')

        LOGGER.debug('Running command: %s', args)
        try:
            subprocess.run(
                args,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            LOGGER.error(
                'Command `%s` failed with return code %s',
                ' '.join(args),
                e.returncode,
            )
            raise SystemExit(e.returncode)

        return

    # we have to call get_all_apps first, then call build_apps(apps)
    test_related_apps, non_test_related_apps = get_all_apps(
        paths,
        target,
        profiles=profiles,
        modified_files=modified_files,
        modified_components=modified_components,
    )

    if test_related:
        return build_apps(
            sorted(test_related_apps),
            parallel_count=parallel_count,
            parallel_index=parallel_index,
            dry_run=dry_run,
        )

    if non_test_related:
        return build_apps(
            sorted(non_test_related_apps),
            parallel_count=parallel_count,
            parallel_index=parallel_index,
            dry_run=dry_run,
        )
