# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import typing as t

if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict  # noqa

PathLike = t.Union[str, os.PathLike]


class UndefinedType:
    def __repr__(self) -> str:
        return '__UNDEF__'


UNDEF = UndefinedType()
T = t.TypeVar('T')
UndefinedOr = t.Union[UndefinedType, T]


def is_undefined(value: t.Any) -> bool:
    """Check if a value is undefined.

    :param value: The value to check

    :returns: True if the value equals the UNDEF constant, False otherwise
    """
    return isinstance(value, UndefinedType) or value == '__UNDEF__'  # click would convert UNDEF to '__UNDEF__'


def is_defined_and_satisfies(value: t.Any, _callable: t.Callable[[t.Any], bool] = bool) -> bool:
    """Check if a value is defined and the callable returns True for the value.

    :param value: The value to check
    :param _callable: The callable to check the value with. Default is ``bool()``

    :returns: True if the value is defined and the callable returns True for the value,
        False otherwise
    """
    return not is_undefined(value) and _callable(value)
