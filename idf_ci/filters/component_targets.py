# SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from idf_ci.settings import get_ci_settings

logger = logging.getLogger(__name__)


def _normalized_path(path: str) -> str:
    raw_path = Path(path)
    if not raw_path.is_absolute():
        return raw_path.as_posix()

    settings = get_ci_settings()
    abs_path = raw_path.as_posix()

    try:
        return Path(abs_path).relative_to(settings.project_root).as_posix()
    except ValueError:
        return abs_path


def _component_mapping_search_path(path: str) -> str:
    search_path = path if path.startswith('/') else f'/{path}'
    return f'{search_path.rstrip("/")}/'


def _component_mapping_for_path(path: str) -> Optional[Tuple[str, str, str]]:
    settings = get_ci_settings()
    normalized_path = _normalized_path(path)
    candidate = _component_mapping_search_path(normalized_path)

    for regex in settings.all_component_mapping_regexes:
        match = regex.search(candidate)
        if not match:
            continue

        root = candidate[: match.end()].rstrip('/')
        if not normalized_path.startswith('/'):
            root = root.lstrip('/')

        return match.group(1), root, normalized_path

    return None


def folder_for_path(path: str) -> str:
    return path.rsplit('/', 1)[0] if '/' in path else path


def collapse_folders(folders: Iterable[str]) -> List[str]:
    collapsed: List[str] = []

    for folder in sorted(set(folders), key=lambda item: (item.count('/'), item)):
        if any(folder == root or folder.startswith(root + '/') for root in collapsed):
            continue
        collapsed.append(folder)

    return collapsed


def extract_targets(path: str) -> Set[str]:
    settings = get_ci_settings()
    candidates = [path]
    if not path.endswith('/'):
        candidates.append(f'{path}/')

    found_targets: Set[str] = set()
    for candidate in candidates:
        for regex in settings.all_component_target_regexes:
            overlapping_regex = re.compile(f'(?={regex.pattern})', regex.flags)
            for match in overlapping_regex.findall(candidate):
                found_targets.add(match[0] if isinstance(match, tuple) else match)

    return found_targets


def targets_for_folders(folders: List[str]) -> List[str]:
    found_targets: Set[str] = set()

    for folder in folders:
        folder_targets = extract_targets(folder)
        if not folder_targets:
            return ['all']
        found_targets.update(folder_targets)

    return sorted(found_targets)


def _is_path_excluded(path: str) -> bool:
    abs_path = Path(os.path.abspath(path)).as_posix()
    settings = get_ci_settings()

    return any(regex.search(abs_path) for regex in settings.all_component_mapping_exclude_regexes)


@lru_cache()
def component_targets_from_files(
    modified_files: Iterable[str],
) -> Dict[str, List[str]]:
    component_groups: Dict[str, Set[str]] = {}

    for path in modified_files:
        if not isinstance(path, str):
            continue

        path = path.strip()
        if not path:
            continue

        if _is_path_excluded(path):
            logger.debug('Skipping excluded path for component mapping: %s', path)
            continue

        component_mapping = _component_mapping_for_path(path)
        if component_mapping is None:
            continue

        component, root, normalized_path = component_mapping
        folder = folder_for_path(normalized_path)
        if not folder.startswith(root):
            folder = root

        component_groups.setdefault(component, set()).add(folder)

    res = {
        component: targets_for_folders(collapse_folders(component_folders))
        for component, component_folders in sorted(component_groups.items())
    }
    logger.debug(
        'Modified files %s: component → target mapping: %s',
        modified_files,
        res,
    )
    return res


def combined_targets_for_components(
    modified_files: Iterable[str],
    check_components: Iterable[str],
) -> List[str]:
    component_targets = component_targets_from_files(tuple(modified_files))
    combined_targets: Set[str] = set()
    if not check_components:
        for k in component_targets:
            targets = component_targets.get(k)
            if not targets:
                continue
            if targets == ['all']:
                return ['all']
            combined_targets.update(targets)

    for component in check_components:
        targets = component_targets.get(component)
        if not targets:
            continue
        if targets == ['all']:
            return ['all']
        combined_targets.update(targets)

    return sorted(combined_targets)


def should_skip_build_for_components(
    modified_files: Iterable[str],
    check_components: Iterable[str],
    current_target: str,
) -> bool:
    targets = combined_targets_for_components(modified_files, check_components)
    should_skip = bool(targets) and 'all' not in targets and current_target not in targets
    return should_skip
