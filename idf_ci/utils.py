# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import typing as t

import rich.logging

_T = t.TypeVar('_T')


@t.overload
def to_list(s: None) -> None: ...


@t.overload
def to_list(s: t.Iterable[_T]) -> t.List[_T]: ...


@t.overload
def to_list(s: _T) -> t.List[_T]: ...


def to_list(s):
    """
    Turn all objects to lists

    :param s: anything
    :return:
        - ``None``, if ``s`` is None
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


def setup_logging(level: t.Optional[int] = logging.WARNING) -> None:
    """
    Setup logging

    :param level: logging level
    """
    package_logger = logging.getLogger(__package__)

    if level is None:
        level = logging.WARNING

    package_logger.setLevel(level)
    package_logger.addHandler(
        rich.logging.RichHandler(
            level=level,
            show_path=False,
        )
    )
    package_logger.propagate = False
