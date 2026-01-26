# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import sys

import pytest

from idf_ci.utils import parse_tuple_from_string, remove_subfolders


@pytest.mark.parametrize(
    'relpaths,expected_relpaths',
    [
        (['a/b/c', 'a/b', 'a', 'a/b/c/d'], ['a']),
        (['b', 'a/b', 'a', 'c/d'], ['a', 'b', 'c/d']),
    ],
)
@pytest.mark.skipif(sys.platform == 'win32', reason='Using Unix paths')
def test_remove_subfolders(tmp_path, relpaths, expected_relpaths):
    paths = []
    for rel in relpaths:
        dir_path = tmp_path / rel
        dir_path.mkdir(parents=True, exist_ok=True)
        paths.append(str(dir_path))
    expected = [(tmp_path / rel) for rel in expected_relpaths]
    assert remove_subfolders(paths) == expected


@pytest.mark.parametrize(
    'input_str,expected',
    [
        ("('a', 'b')", ('a', 'b')),
        ("('a',)", ('a',)),
        ("('a', ('b', 'c'))", ('a', ('b', 'c'))),
        ('(1, 2, 3)', (1, 2, 3)),
    ],
)
def test_parse_tuple_from_string(input_str, expected):
    assert parse_tuple_from_string(input_str) == expected


@pytest.mark.parametrize(
    'input_str,error_match',
    [
        ("['a', 'b']", 'Expected a tuple'),
        ('not a tuple', 'Failed to parse tuple'),
    ],
)
def test_parse_tuple_from_string_error(input_str, error_match):
    with pytest.raises(RuntimeError, match=error_match):
        parse_tuple_from_string(input_str)
