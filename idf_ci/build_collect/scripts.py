# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import typing as t
from collections import defaultdict
from pathlib import Path

from idf_build_apps import find_apps
from idf_build_apps.app import App
from idf_build_apps.args import FindArguments
from idf_build_apps.constants import ALL_TARGETS, BuildStatus
from jinja2 import Environment, FileSystemLoader

from idf_ci import get_pytest_cases
from idf_ci.build_collect.models import (
    AppInfo,
    AppKey,
    AppStatus,
    CaseInfo,
    CollectResult,
    MissingAppInfo,
    ProjectInfo,
)
from idf_ci.idf_pytest import PytestCase

logger = logging.getLogger(__name__)


def normalize_path(path: str) -> str:
    return Path(path).absolute().as_posix()


def collect_build_apps(
    *,
    paths: t.Optional[t.List[str]] = None,
    include_only_enabled: bool = False,
) -> t.Tuple[t.Dict[AppKey, App], t.Dict[str, str]]:
    """Collect all buildable apps from given paths.

    :param paths: Paths to search for apps.
    :param include_only_enabled: If True, include only enabled apps.

    :returns: Tuple of dictionary with apps and mapping of normalized paths to original
        paths.
    """
    find_arguments = FindArguments(
        include_all_apps=not include_only_enabled,
        recursive=True,
        enable_preview_targets=True,
    )

    if paths is not None:
        find_arguments.paths = paths

    apps = find_apps(find_arguments=find_arguments)

    result: t.Dict[AppKey, App] = {}
    paths_mapping: t.Dict[str, str] = {}

    for app in apps:
        # Skip apps without config
        if app.config_name is None:
            continue

        path = app.app_dir
        normalized_path = normalize_path(path)
        paths_mapping[normalized_path] = path

        app_key = AppKey(
            path=normalized_path,
            target=app.target,
            config=app.config_name,
        )
        result[app_key] = app

    return result, paths_mapping


def collect_test_apps(*, paths: t.Optional[t.List[str]] = None) -> t.Dict[AppKey, t.List[PytestCase]]:
    """Collect all apps referenced by pytest test cases from given paths.

    :param paths: Paths to search for test cases.

    :returns: Dictionary with apps containing list of test cases.
    """
    cases = get_pytest_cases(
        paths=paths,
        marker_expr='',
        additional_args=['--ignore-no-tests-collected-error'],
    )

    result: t.Dict[AppKey, t.List[PytestCase]] = defaultdict(list)
    for case in cases:
        for app in case.apps:
            app_key = AppKey(
                path=normalize_path(app.path),
                target=app.target,
                config=app.config,
            )
            if case not in result[app_key]:
                result[app_key].append(case)

    return dict(result)


AppValue = t.TypeVar('AppValue')


def group_by_path(apps: t.Dict[AppKey, AppValue]) -> t.Dict[str, t.Dict[AppKey, AppValue]]:
    """Group apps by path.

    :param apps: Dictionary with apps.

    :returns: Dictionary grouped by path.
    """
    result: t.Dict[str, t.Dict[AppKey, AppValue]] = defaultdict(dict)
    for app_key, value in apps.items():
        result[app_key.path][app_key] = value
    return dict(result)


def enabled_test_targets(app: App) -> t.List[str]:
    """List of enabled test targets for the app.

    :param app: App instance.

    :returns: List of enabled test targets.
    """
    if app.MANIFEST is None:
        return list(ALL_TARGETS)

    return app.MANIFEST.enable_test_targets(app.app_dir, config_name=app.config_name)


def create_test_case_info(test_case: PytestCase, app: App):
    """Create information about test case for given app.

    :param test_case: PytestCase instance.
    :param app: App instance.

    :returns: CaseInfo instance.
    """
    enabled_targets = enabled_test_targets(app)
    skipped_targets = test_case.skipped_targets()

    disabled_by_manifest = app.target not in enabled_targets
    disabled_by_marker = app.target in skipped_targets
    disabled = disabled_by_manifest or disabled_by_marker

    skip_reason = skipped_targets.get(app.target, '')
    test_comment = app.test_comment or ''

    return CaseInfo(
        name=test_case.name,
        caseid=test_case.caseid,
        disabled=disabled,
        disabled_by_manifest=disabled_by_manifest,
        disabled_by_marker=disabled_by_marker,
        skip_reason=skip_reason,
        test_comment=test_comment,
    )


def create_test_case_missing_app_info(
    test_case: PytestCase,
    target: str,
):
    """Create information about test case with missing app.

    :param test_case: PytestCase instance.
    :param target: Target name.

    :returns: CaseInfo instance.
    """
    skipped_targets = test_case.skipped_targets()

    disabled_by_marker = target in skipped_targets
    disabled = disabled_by_marker

    skip_reason = skipped_targets.get(target, '')

    return CaseInfo(
        name=test_case.name,
        caseid=test_case.caseid,
        disabled=disabled,
        disabled_by_marker=disabled_by_marker,
        skip_reason=skip_reason,
    )


def matched_rules(app: App) -> t.Dict[str, t.List[str]]:
    if app.MANIFEST is None:
        return {}

    rule = app.MANIFEST.most_suitable_rule(app.app_dir)
    config_name = app.config_name or 'default'
    matched = {
        'enable': [str(clause) for clause in rule.enable if clause.get_value(app.target, config_name)],
        'disable': [str(clause) for clause in rule.disable if clause.get_value(app.target, config_name)],
        'disable_test': [str(clause) for clause in rule.disable_test if clause.get_value(app.target, config_name)],
    }

    if any(matched.values()):
        return matched

    return {}


def has_temporary_rule(app: App) -> bool:
    if app.MANIFEST is None:
        return False

    rule = app.MANIFEST.most_suitable_rule(app.app_dir)
    config_name = app.config_name or 'default'

    return any(
        clause.temporary and clause.get_value(app.target, config_name)
        for clause in [*rule.enable, *rule.disable, *rule.disable_test]
    )


def process_apps(
    build_apps: t.Dict[AppKey, App],
    test_apps: t.Dict[AppKey, t.List[PytestCase]],
) -> t.Tuple[
    t.List[AppInfo],
    t.Set[str],
    t.Set[str],
]:
    """Process buildable apps and attach test cases.

    :param build_apps: Dictionary with buildable apps.
    :param test_apps: Dictionary with apps referenced by test cases.

    :returns: Tuple of info about apps, used test cases, and disabled test cases.
    """
    result: t.List[AppInfo] = []
    used_test_cases: t.Set[str] = set()
    disabled_test_cases: t.Set[str] = set()

    for app_key, app in build_apps.items():
        test_cases = test_apps.get(app_key, [])
        test_case_info_list: t.List[CaseInfo] = []

        # Process test cases
        for case in test_cases:
            info = create_test_case_info(case, app)
            test_case_info_list.append(info)

            if info.disabled:
                disabled_test_cases.add(case.caseid)
            else:
                used_test_cases.add(case.caseid)

        result.append(
            AppInfo(
                target=app_key.target,
                config=app_key.config,
                build_status=app.build_status,
                build_comment=app.build_comment or '',
                test_comment=app.test_comment or '',
                test_cases=test_case_info_list,
                has_temp_rule=has_temporary_rule(app),
                matched_rules=matched_rules(app),
            )
        )

    return result, used_test_cases, disabled_test_cases


def process_missing_apps(
    build_apps: t.Dict[AppKey, App],
    test_apps: t.Dict[AppKey, t.List[PytestCase]],
) -> t.Tuple[
    t.List[MissingAppInfo],
    t.Set[str],
]:
    """Find and process missing apps referenced by test cases.

    :param build_apps: Dictionary with buildable apps.
    :param test_apps: Dictionary with apps referenced by test cases.

    :returns: Tuple of info about missing apps and their test cases.
    """
    result: t.List[MissingAppInfo] = []
    missing_app_test_cases: t.Set[str] = set()
    missing_keys = set(test_apps.keys()) - set(build_apps.keys())

    for app_key in sorted(missing_keys):
        test_cases = test_apps[app_key]
        test_case_info_list: t.List[CaseInfo] = []

        # Process test cases
        for case in test_cases:
            info = create_test_case_missing_app_info(case, app_key.target)
            test_case_info_list.append(info)
            missing_app_test_cases.add(case.caseid)

        result.append(
            MissingAppInfo(
                target=app_key.target,
                config=app_key.config,
                test_cases=test_case_info_list,
            )
        )

    return result, missing_app_test_cases


def collect_apps(
    *,
    paths: t.Optional[t.List[str]] = None,
    include_only_enabled: bool = False,
) -> CollectResult:
    """Collect all apps and their corresponding test cases.

    :param paths: Paths to search.
    :param include_only_enabled: If True, only include enabled apps.

    :returns: CollectResult instance.
    """
    logger.debug('Collecting apps from paths')
    build_apps, paths_mapping = collect_build_apps(paths=paths, include_only_enabled=include_only_enabled)

    logger.debug('Collecting apps referenced by test cases')
    test_apps = collect_test_apps(paths=paths)

    build_apps_by_path = group_by_path(build_apps)
    test_apps_by_path = group_by_path(test_apps)

    result = CollectResult()
    project_paths = list(build_apps_by_path.keys())

    logger.debug('Processing apps')
    for index, path in enumerate(sorted(project_paths)):
        original_path = paths_mapping[path]

        logger.debug(
            f'Processing path {index + 1}/{len(project_paths)} '
            f'with {len(build_apps_by_path[path])} apps: {original_path}'
        )

        project_build_apps = build_apps_by_path.get(path, {})
        project_test_apps = test_apps_by_path.get(path, {})

        app_info, used_test_cases, disabled_test_cases = process_apps(
            project_build_apps,
            project_test_apps,
        )

        missing_app_info, missing_app_test_cases = process_missing_apps(
            project_build_apps,
            project_test_apps,
        )

        result.projects[original_path] = ProjectInfo(
            apps=app_info,
            missing_apps=missing_app_info,
        )

        result.summary.total_test_cases_used += len(used_test_cases)
        result.summary.total_test_cases_disabled += len(disabled_test_cases)
        result.summary.total_test_cases_missing_app += len(missing_app_test_cases)
        result.summary.total_test_cases += len(used_test_cases | disabled_test_cases | missing_app_test_cases)

    result.summary.total_projects = len(project_paths)
    result.summary.total_apps = len(build_apps)

    return result


def format_as_json(result: CollectResult) -> str:
    """Format result as JSON.

    :param result: CollectResult instance.
    """
    return result.model_dump_json()


def format_as_html(result: CollectResult) -> str:
    """Format result as HTML.

    :param result: CollectResult instance.
    """
    rows = []
    all_targets: t.Set[str] = set()

    for project_path, project in result.projects.items():
        # Build mapping (target, config) -> app
        config_target_app: t.Dict[t.Tuple[str, str], AppInfo] = {}
        target_list: t.Set[str] = set()
        config_list: t.Set[str] = set()

        for app in project.apps:
            config_target_app[(app.target, app.config)] = app
            target_list.add(app.target)
            config_list.add(app.config)

        all_targets.update(target_list)
        config_list_sorted = sorted(config_list)
        target_list_sorted = sorted(target_list)

        total_tests = 0
        total_enabled_tests = 0
        details = []

        for config in config_list_sorted:
            detail_item: t.Dict[str, t.Any] = {'sdkconfig': config, 'coverage': 0, 'targets': []}
            targets_tested = 0
            targets_total = 0

            for target in target_list_sorted:
                target_info = create_target_info(target, config_target_app.get((target, config)))
                detail_item['targets'].append(target_info)

                if target_info['status'] != AppStatus.UNKNOWN:
                    targets_total += 1
                    if target_info['enabled_tests'] > 0:
                        targets_tested += 1

                total_tests += target_info['tests']
                total_enabled_tests += target_info['enabled_tests']

            if targets_total > 0:
                detail_item['coverage'] = (targets_tested / targets_total) * 100

            details.append(detail_item)

        # Collect test cases with missing apps (unknown sdkconfig)
        tests_unknown_sdkconfig = [tc.caseid for app in project.missing_apps for tc in app.test_cases]

        rows.append(
            {
                'project_path': project_path,
                'apps': len(project.apps),
                'tests': total_tests,
                'enabled_tests': total_enabled_tests,
                'tests_unknown_sdkconfig': tests_unknown_sdkconfig,
                'target_list': target_list_sorted,
                'details': details,
            }
        )

    rows = sorted(rows, key=lambda x: str(x['project_path']))

    loader = FileSystemLoader(Path(__file__).parent)
    env = Environment(loader=loader)
    template = env.get_template('template.html')

    return template.render(
        {
            'targets': sorted(all_targets),
            'rows': rows,
        }
    )


def create_target_info(target: str, app: t.Optional[AppInfo]) -> t.Dict[str, t.Any]:
    """Create information about target for HTML format.

    :param target: Target name.
    :param app: AppInfo instance or None if app is missing.

    :returns: Dictionary with target information.
    """
    info: t.Dict[str, t.Any] = {
        'name': target,
        'status': AppStatus.UNKNOWN,
        'status_label': '',
        'has_err': False,
        'is_disabled': False,
        'disable_reason': '',
        'tests': 0,
        'enabled_tests': 0,
        'has_temp_rule': False,
        'matched_rules': {},
    }

    if app is None:
        return info

    test_cases = app.test_cases
    disabled_cases = [tc for tc in test_cases if tc.disabled]
    enabled_count = len(test_cases) - len(disabled_cases)
    disabled_count = len(disabled_cases)

    info['tests'] = len(test_cases)
    info['enabled_tests'] = enabled_count

    # Determine status
    has_enabled_tests = enabled_count > 0
    has_skipped_tests = disabled_count > 0
    is_disabled = app.build_status == BuildStatus.DISABLED

    if is_disabled:
        info['is_disabled'] = True
        info['disable_reason'] = app.build_comment

    # Map (is_disabled, has_enabled_tests, has_skipped_tests) to AppStatus
    status_map = {
        (False, False, False): AppStatus.SHOULD_BE_BUILT,
        (False, True, False): AppStatus.SHOULD_BE_BUILT_AND_TESTS_ENABLED,
        (False, False, True): AppStatus.SHOULD_BE_BUILT_AND_TESTS_SKIPPED,
        (False, True, True): AppStatus.SHOULD_BE_BUILT_AND_TESTS_MIXED,
        (True, False, False): AppStatus.DISABLED,
        (True, True, False): AppStatus.DISABLED_AND_TESTS_ENABLED,
        (True, False, True): AppStatus.DISABLED_AND_TESTS_SKIPPED,
        (True, True, True): AppStatus.DISABLED_AND_TESTS_MIXED,
    }

    info['status'] = status_map[(is_disabled, has_enabled_tests, has_skipped_tests)]
    info['status_label'] = AppStatus.DISABLED if is_disabled else AppStatus.SHOULD_BE_BUILT
    info['has_temp_rule'] = app.has_temp_rule
    info['matched_rules'] = app.matched_rules

    # Check for mismatches
    disabled_by_manifest_only = [tc for tc in test_cases if tc.disabled_by_manifest and not tc.disabled_by_marker]
    disabled_by_marker_only = [tc for tc in test_cases if tc.disabled_by_marker and not tc.disabled_by_manifest]

    if disabled_by_manifest_only or disabled_by_marker_only:
        info['has_err'] = True
        info['disabled_by_manifest_only'] = [tc.model_dump() for tc in disabled_by_manifest_only]
        info['disabled_by_marker_only'] = [tc.model_dump() for tc in disabled_by_marker_only]

    return info
