# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import sys

import pytest

from idf_ci.utils import remove_subfolders


@pytest.mark.parametrize(
    'paths,expected',
    [
        (['/a/b/c', '/a/b', '/a', '/a/b/c/d'], ['/a']),
        (['/b', '/a/b', '/a', '/c/d'], ['/a', '/b', '/c/d']),
    ],
)
@pytest.mark.skipif(sys.platform == 'win32', reason='Using Unix paths')
def test_remove_subfolders(paths, expected):
    assert remove_subfolders(paths) == expected
