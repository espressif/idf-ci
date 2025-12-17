# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import typing as t
from pathlib import Path

from idf_build_apps import find_apps
from idf_build_apps.app import App
from idf_build_apps.args import FindArguments
from idf_build_apps.constants import ALL_TARGETS, BuildStatus
from jinja2 import Environment, FileSystemLoader

from idf_ci import get_pytest_cases
from idf_ci.idf_pytest import PytestCase

logger = logging.getLogger(__name__)


def collect_apps(paths: t.List[str], include_only_enabled_apps: bool) -> t.Dict[str, t.Any]:
    """Collect all applications and corresponding test cases."""
    apps = find_apps(
        find_arguments=FindArguments(
            paths=paths,
            include_all_apps=not include_only_enabled_apps,
            recursive=True,
            enable_preview_targets=True,
        ),
    )

    test_cases = get_pytest_cases(
        paths=paths,
        marker_expr='',  # pass empty marker to collect all test cases
        additional_args=['--ignore-no-tests-collected-error'],
    )

    # Gather apps by path
    apps_by_path: t.Dict[str, t.List[App]] = {}
    apps_by_abs_path: t.Dict[str, t.List[App]] = {}
    for app in apps:
        apps_by_path.setdefault(app.app_dir, []).append(app)
        apps_by_abs_path.setdefault(Path(app.app_dir).absolute().as_posix(), []).append(app)

    # Create a dict with test cases for quick lookup
    # Structure: path -> target -> sdkconfig -> list[PytestCase]
    test_cases_index: t.Dict[str, t.Dict[str, t.Dict[str, t.List[PytestCase]]]] = {}
    for case in test_cases:
        case_path = Path(case.path).parent.as_posix()

        # Handle multiple targets
        targets = case.targets
        for target in targets:
            test_cases_index.setdefault(case_path, {}).setdefault(target, {})

            for pytest_app in case.apps:
                test_cases_index[case_path][target].setdefault(pytest_app.config, [])
                test_cases_index[case_path][target][pytest_app.config].append(case)

    result: t.Dict[str, t.Any] = {
        'summary': {
            'total_projects': len(apps_by_path),
            'total_apps': len(apps),
            'total_test_cases': len(test_cases),
            'total_test_cases_used': 0,
            'total_test_cases_disabled': 0,
            'total_test_cases_requiring_nonexistent_app': 0,
        },
        'projects': {},
    }

    for index, app_path in enumerate(sorted(apps_by_path)):
        logger.debug(
            f'Processing path {index + 1}/{len(apps_by_path)} with {len(apps_by_path[app_path])} apps: {app_path}'
        )

        result['projects'][app_path] = {'apps': [], 'test_cases_requiring_nonexistent_app': []}
        project: t.Dict[str, t.Any] = result['projects'][app_path]
        project_test_cases: t.Set[str] = set()
        used_test_cases: t.Set[str] = set()
        disabled_test_cases: t.Set[str] = set()
        app_abs_path = Path(app_path).absolute().as_posix()

        for app in apps_by_path[app_path]:
            # Find test cases for current app by path, target and sdkconfig
            app_test_cases: t.Dict[str, PytestCase] = {}

            if app_abs_path in test_cases_index:
                # Gather all test cases
                for target_key in test_cases_index[app_abs_path]:
                    for sdkconfig_key in test_cases_index[app_abs_path][target_key]:
                        test_cases = test_cases_index[app_abs_path][target_key][sdkconfig_key]
                        project_test_cases.update([case.caseid for case in test_cases])

                # Find matching test cases
                if app.target in test_cases_index[app_abs_path]:
                    if app.config_name in test_cases_index[app_abs_path][app.target]:
                        test_cases = test_cases_index[app_abs_path][app.target][app.config_name]

                        for case in test_cases:
                            app_test_cases[case.caseid] = case

            # Get enabled test targets from manifest if exists
            enabled_test_targets = ALL_TARGETS
            if app.MANIFEST is not None:
                enabled_test_targets = app.MANIFEST.enable_test_targets(app_path, config_name=app.config_name)

            # Test cases info
            test_cases_info: t.List[t.Dict[str, t.Any]] = []
            for case in app_test_cases.values():
                test_case: t.Dict[str, t.Any] = {
                    'name': case.name,
                    'caseid': case.caseid,
                }

                skipped_targets = case.skipped_targets()
                is_disabled_by_manifest = app.target not in enabled_test_targets
                is_disabled_by_marker = app.target in skipped_targets

                if is_disabled_by_manifest or is_disabled_by_marker:
                    test_case['disabled'] = True
                    test_case['disabled_by_manifest'] = is_disabled_by_manifest
                    test_case['disabled_by_marker'] = is_disabled_by_marker

                    if is_disabled_by_marker:
                        test_case['skip_reason'] = skipped_targets[app.target]

                    if is_disabled_by_manifest:
                        test_case['test_comment'] = app.test_comment or ''

                    disabled_test_cases.add(case.caseid)
                else:
                    used_test_cases.add(case.caseid)

                test_cases_info.append(test_case)

            project['apps'].append(
                {
                    'target': app.target,
                    'sdkconfig': app.config_name,
                    'build_status': app.build_status.value,
                    'build_comment': app.build_comment or '',
                    'test_comment': app.test_comment or '',
                    'test_cases': test_cases_info,
                }
            )

        unused_test_cases: t.Set[str] = project_test_cases.copy()
        unused_test_cases.difference_update(used_test_cases)
        unused_test_cases.difference_update(disabled_test_cases)

        for unused_test_case in unused_test_cases:
            project['test_cases_requiring_nonexistent_app'].append(unused_test_case)

        result['summary']['total_test_cases_used'] += len(used_test_cases)
        result['summary']['total_test_cases_disabled'] += len(disabled_test_cases)
        result['summary']['total_test_cases_requiring_nonexistent_app'] += len(unused_test_cases)

    return result


def format_as_json(data: t.Dict[str, t.Any]) -> str:
    """Format collected data as JSON."""
    return json.dumps(data)


def format_as_html(data: t.Dict[str, t.Any]) -> str:
    """Format collected data as HTML."""
    rows = []
    projects = data.get('projects', {})
    all_target_list = set()

    for project_path, project_info in projects.items():
        apps = project_info.get('apps', [])

        total_tests = 0
        total_enabled_tests = 0
        target_list = set()
        config_list = set()
        config_target_app: t.Dict[str, t.Dict[str, t.Any]] = {}
        details = []

        for app in apps:
            # Collect sdkconfigs
            config_list.add(app.get('sdkconfig'))

            # Collect targets
            target_list.add(app.get('target'))

            # config -> target -> app
            config_target_app.setdefault(app.get('sdkconfig'), {})[app.get('target')] = app

        all_target_list.update(target_list)
        config_list_sorted = sorted(config_list)
        target_list_sorted = sorted(target_list)

        for config in config_list_sorted:
            detail_item = {'sdkconfig': config, 'coverage': 0, 'targets': []}

            targets_tested = 0
            targets_total = 0

            for target in target_list_sorted:
                # Status:
                # U - Unknown
                # B - Should be built
                # D - Disabled
                # T - Tests enabled
                # S - Tests skipped
                target_info = {
                    'name': target,
                    'status': 'U',
                    'status_label': '',  # B - Should be built, D - Disabled
                    'has_err': False,
                    'is_disabled': False,
                    'disable_reason': '',
                    'tests': 0,
                    'enabled_tests': 0,
                }

                app = config_target_app.get(config, {}).get(target)

                if app:
                    targets_total += 1

                    status = app.get('build_status')
                    test_cases = app.get('test_cases', [])
                    disabled_test_cases = [case for case in test_cases if case.get('disabled')]

                    target_info['tests'] = len(test_cases)
                    target_info['enabled_tests'] = target_info['tests'] - len(disabled_test_cases)

                    total_tests += target_info['tests']
                    total_enabled_tests += target_info['enabled_tests']

                    if status == BuildStatus.DISABLED:
                        target_info['status'] = target_info['status_label'] = 'D'
                        target_info['is_disabled'] = True
                        target_info['disable_reason'] = app.get('build_comment', '')
                    elif status == BuildStatus.SHOULD_BE_BUILT:
                        target_info['status'] = target_info['status_label'] = 'B'

                    if target_info['enabled_tests'] > 0:
                        target_info['status'] += 'T'
                        targets_tested += 1

                    if len(disabled_test_cases) > 0:
                        target_info['status'] += 'S'

                    # Mismatched test cases
                    disabled_by_manifest_only = [
                        case
                        for case in test_cases
                        if case.get('disabled_by_manifest') and not case.get('disabled_by_marker')
                    ]
                    disabled_by_marker_only = [
                        case
                        for case in test_cases
                        if case.get('disabled_by_marker') and not case.get('disabled_by_manifest')
                    ]

                    # Set error if there are any mismatches
                    if disabled_by_manifest_only or disabled_by_marker_only:
                        target_info['has_err'] = True
                        target_info['disabled_by_manifest_only'] = disabled_by_manifest_only
                        target_info['disabled_by_marker_only'] = disabled_by_marker_only

                detail_item['targets'].append(target_info)

            if targets_total > 0:
                detail_item['coverage'] = (targets_tested / targets_total) * 100

            details.append(detail_item)

        rows.append(
            {
                'project_path': project_path,
                'apps': len(apps),
                'tests': total_tests,
                'enabled_tests': total_enabled_tests,
                'tests_unknown_sdkconfig': project_info.get('test_cases_requiring_nonexistent_app', []),
                'target_list': target_list_sorted,
                'details': details,
            }
        )

    rows = sorted(rows, key=lambda x: x['project_path'])
    loader = FileSystemLoader(Path(__file__).parent)
    env = Environment(loader=loader)
    template = env.get_template('template.html')
    output = template.render(
        {
            'targets': sorted(all_target_list),
            'rows': rows,
        }
    )

    return output
