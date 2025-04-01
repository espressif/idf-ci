# This file contains snippets from various files in the repository. Attached the LICENSE file accordingly.
import functools
import os
import re

# The `glob.translate` function is introduced in python 3.13.
# Copying the implementation from the Python 3.13 source code.


# This `translate` function is taken from
# https://github.com/python/cpython/blob/2c8f329dc634290fb88636f85c05e473bc0104d5/Lib/glob.py#L267
# following the license terms of the Python Software Foundation License Version 2.
def translate(pat, *, recursive=False, include_hidden=False, seps=None):
    """Translate a pathname with shell wildcards to a regular expression.

    If `recursive` is true, the pattern segment '**' will match any number of path
    segments.

    If `include_hidden` is true, wildcards can match path segments beginning with a dot
    ('.').

    If a sequence of separator characters is given to `seps`, they will be used to split
    the pattern into segments and match path separators. If not given, os.path.sep and
    os.path.altsep (where available) are used.
    """
    if not seps:
        if os.path.altsep:
            seps = (os.path.sep, os.path.altsep)
        else:
            seps = os.path.sep
    escaped_seps = ''.join(map(re.escape, seps))
    any_sep = f'[{escaped_seps}]' if len(seps) > 1 else escaped_seps
    not_sep = f'[^{escaped_seps}]'
    if include_hidden:
        one_last_segment = f'{not_sep}+'
        one_segment = f'{one_last_segment}{any_sep}'
        any_segments = f'(?:.+{any_sep})?'
        any_last_segments = '.*'
    else:
        one_last_segment = f'[^{escaped_seps}.]{not_sep}*'
        one_segment = f'{one_last_segment}{any_sep}'
        any_segments = f'(?:{one_segment})*'
        any_last_segments = f'{any_segments}(?:{one_last_segment})?'

    results = []
    parts = re.split(any_sep, pat)
    last_part_idx = len(parts) - 1
    for idx, part in enumerate(parts):
        if part == '*':
            results.append(one_segment if idx < last_part_idx else one_last_segment)
        elif recursive and part == '**':
            if idx < last_part_idx:
                if parts[idx + 1] != '**':
                    results.append(any_segments)
            else:
                results.append(any_last_segments)
        else:
            if part:
                if not include_hidden and part[0] in '*?':
                    results.append(r'(?!\.)')
                results.extend(_fnmatch_translate(part, f'{not_sep}*', not_sep)[0])
            if idx < last_part_idx:
                results.append(any_sep)
    res = ''.join(results)
    return rf'(?s:{res})\Z'


# This `_re_setops_sub` function is taken from
# https://github.com/python/cpython/blob/2c8f329dc634290fb88636f85c05e473bc0104d5/Lib/fnmatch.py#L83
# following the license terms of the Python Software Foundation License Version 2.
_re_setops_sub = re.compile(r'([&~|])').sub

# This `_re_escape` function is taken from
# https://github.com/python/cpython/blob/2c8f329dc634290fb88636f85c05e473bc0104d5/Lib/fnmatch.py#L84
# following the license terms of the Python Software Foundation License Version 2.
_re_escape = functools.lru_cache(maxsize=512)(re.escape)


# This `_fnmatch_translate` function is taken from
# https://github.com/python/cpython/blob/2c8f329dc634290fb88636f85c05e473bc0104d5/Lib/fnmatch.py#L86
# following the license terms of the Python Software Foundation License Version 2.
def _fnmatch_translate(pat, star, question_mark):
    res = []
    add = res.append
    star_indices = []

    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        i = i + 1
        if c == '*':
            # store the position of the wildcard
            star_indices.append(len(res))
            add(star)
            # compress consecutive `*` into one
            while i < n and pat[i] == '*':
                i += 1
        elif c == '?':
            add(question_mark)
        elif c == '[':
            j = i
            if j < n and pat[j] == '!':
                j = j + 1
            if j < n and pat[j] == ']':
                j = j + 1
            while j < n and pat[j] != ']':
                j = j + 1
            if j >= n:
                add('\\[')
            else:
                stuff = pat[i:j]
                if '-' not in stuff:
                    stuff = stuff.replace('\\', r'\\')
                else:
                    chunks = []
                    k = i + 2 if pat[i] == '!' else i + 1
                    while True:
                        k = pat.find('-', k, j)
                        if k < 0:
                            break
                        chunks.append(pat[i:k])
                        i = k + 1
                        k = k + 3
                    chunk = pat[i:j]
                    if chunk:
                        chunks.append(chunk)
                    else:
                        chunks[-1] += '-'
                    # Remove empty ranges -- invalid in RE.
                    for k in range(len(chunks) - 1, 0, -1):
                        if chunks[k - 1][-1] > chunks[k][0]:
                            chunks[k - 1] = chunks[k - 1][:-1] + chunks[k][1:]
                            del chunks[k]
                    # Escape backslashes and hyphens for set difference (--).
                    # Hyphens that create ranges shouldn't be escaped.
                    stuff = '-'.join(s.replace('\\', r'\\').replace('-', r'\-') for s in chunks)
                i = j + 1
                if not stuff:
                    # Empty range: never match.
                    add('(?!)')
                elif stuff == '!':
                    # Negated empty range: match any character.
                    add('.')
                else:
                    # Escape set operations (&&, ~~ and ||).
                    stuff = _re_setops_sub(r'\\\1', stuff)
                    if stuff[0] == '!':
                        stuff = '^' + stuff[1:]
                    elif stuff[0] in ('^', '['):
                        stuff = '\\' + stuff
                    add(f'[{stuff}]')
        else:
            add(_re_escape(c))
    assert i == n
    return res, star_indices
