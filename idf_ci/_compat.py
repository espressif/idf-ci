# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import typing as t

PathLike = t.Union[str, os.PathLike]


UNDEF = '__UNDEF__'


def is_undefined(value: t.Any) -> bool:
    return value == UNDEF
