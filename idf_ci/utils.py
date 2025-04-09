# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import subprocess
import typing as t
from pathlib import Path

from idf_build_apps.log import get_rich_log_handler

_T = t.TypeVar('_T')


@t.overload
def to_list(s: None) -> None: ...


@t.overload
def to_list(s: t.Iterable[_T]) -> t.List[_T]: ...


@t.overload
def to_list(s: _T) -> t.List[_T]: ...


def to_list(s):
    """Turn all objects to lists

    :param s: anything

    :returns: - ``None``, if ``s`` is None
        - itself, if ``s`` is a list
        - ``list(s)``, if ``s`` is a tuple or a set
        - ``[s]``, if ``s`` is other type
    """
    if s is None:
        return s

    if isinstance(s, list):
        return s

    if isinstance(s, set) or isinstance(s, tuple):
        return list(s)

    return [s]


def setup_logging(level: t.Optional[int] = logging.INFO) -> None:
    """Setup logging

    :param level: logging level
    """
    if level is None:
        level = logging.INFO

    package_logger = logging.getLogger(__package__)
    package_logger.setLevel(level)

    if package_logger.hasHandlers():
        package_logger.handlers.clear()
    package_logger.addHandler(get_rich_log_handler(level))

    package_logger.propagate = False


def remove_subfolders(paths: t.List[str]) -> t.List[str]:
    """Remove paths that are subfolders of other paths in the list.

    :param paths: List of directory paths as strings

    :returns: Filtered list of paths with no subfolder/parent folder relationships
    """
    result = set()

    for p in sorted([Path(p).resolve() for p in paths]):
        if not any(parent in result for parent in p.parents):
            result.add(p)

    return sorted([str(p) for p in result])


def get_current_branch() -> str:
    """Get the current Git branch by running git command.

    :returns: The current Git ref (branch name or commit SHA)

    :raises RuntimeError: If not in a Git repository or git command fails
    """
    result = subprocess.run(
        ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
        check=True,
        capture_output=True,
        encoding='utf-8',
    )
    branch = result.stdout.strip()

    # If in detached HEAD state, rev-parse returns "HEAD"
    if branch == 'HEAD':
        raise RuntimeError('Failed to get current Git ref. Are you in a Git repository?')

    return branch
