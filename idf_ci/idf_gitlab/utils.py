# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import re
import typing as t

import yaml


def dynamic_pipeline_variables() -> t.Dict[str, str]:
    """Extract pipeline variables from a GitLab merge request description."""
    description = os.getenv('CI_MERGE_REQUEST_DESCRIPTION', '')
    if not description:
        return {}

    pattern = r'^## Dynamic Pipeline Configuration(?:[^`]*?)```(?:\w+)(.*?)```'
    result = re.search(pattern, description, re.DOTALL | re.MULTILINE)
    if not result:
        return {}

    data = yaml.safe_load(result.group(1))
    res = {}
    if 'Test Case Filters' in data:
        res['DYNAMIC_PIPELINE_FILTER_EXPR'] = ' or '.join(data.get('Test Case Filters'))

    if res:
        res['IS_DEBUG_PIPELINE'] = '1'

    return res
