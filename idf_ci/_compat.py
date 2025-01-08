# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import typing as t

PathLike = t.Union[str, os.PathLike]


class Undefined(str):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, 'undefined')


UNDEF = Undefined()
