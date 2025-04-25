# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import re
import typing as t

import yaml

logger = logging.getLogger(__name__)


def pipeline_variables() -> t.Dict[str, str]:
    """Extract pipeline variables from Gitlab MR predefined variables.

    Possibly set the following variables:

    - IDF_CI_IS_DEBUG_PIPELINE

      Set to '1' if the pipeline is a debug pipeline, will fail at the last stage.

    - IDF_CI_SELECT_ALL_PYTEST_CASES

      Selecting all pytest cases to run

    - IDF_CI_SELECT_BY_FILTER_EXPR

      Build and test only the test cases that match the filter expression (pytest -k)

    - PIPELINE_COMMIT_SHA

      Real commit SHA, instead of the merged result commit SHA

    - INCLUDE_NIGHTLY_RUN

      Run all test cases with or without `nightly_run` marker

    - NIGHTLY_RUN

      Run only test cases with `nightly_run` marker, by default, test cases with
      `nightly_run` marker are skipped
    """
    res: t.Dict[str, str] = {}

    # non-MR pipelines
    if os.getenv('CI_MERGE_REQUEST_IID') is None:
        res['IDF_CI_SELECT_ALL_PYTEST_CASES'] = '1'
        logger.info('Setting `IDF_CI_SELECT_ALL_PYTEST_CASES=1` since running in a non-MR pipeline')

        if os.getenv('CI_COMMIT_SHA'):
            res['PIPELINE_COMMIT_SHA'] = os.environ['CI_COMMIT_SHA']
            logger.info('Setting `PIPELINE_COMMIT_SHA` to `CI_COMMIT_SHA` since running in a non-MR pipeline')
        return res

    if os.getenv('CI_MERGE_REQUEST_SOURCE_BRANCH_SHA'):
        res['PIPELINE_COMMIT_SHA'] = os.environ['CI_MERGE_REQUEST_SOURCE_BRANCH_SHA']
        logger.info('Setting `PIPELINE_COMMIT_SHA` to `CI_MERGE_REQUEST_SOURCE_BRANCH_SHA`')

    if os.getenv('CI_PYTHON_CONSTRAINT_BRANCH'):
        res['IDF_CI_SELECT_ALL_PYTEST_CASES'] = '1'
        logger.info(
            'Setting `IDF_CI_SELECT_ALL_PYTEST_CASES=1` since pipeline is triggered with a python constraint branch'
        )
    else:
        mr_labels = os.getenv('CI_MERGE_REQUEST_LABELS', '').split(',')
        if 'include_nightly_run' in mr_labels:
            res['INCLUDE_NIGHTLY_RUN'] = '1'
            logger.info('Setting `INCLUDE_NIGHTLY_RUN=1` since MR label `include_nightly_run` is set')
            res['NIGHTLY_RUN'] = '1'
            logger.info('Setting `NIGHTLY_RUN=1` since MR label `include_nightly_run` is set')

        if 'nightly' in mr_labels:
            res['NIGHTLY_RUN'] = '1'
            logger.info('Setting `NIGHTLY_RUN=1` since MR label `nightly` is set')

        if 'BUILD_AND_TEST_ALL_APPS' in mr_labels:
            res['IDF_CI_SELECT_ALL_PYTEST_CASES'] = '1'
            logger.info('Setting `IDF_CI_SELECT_ALL_PYTEST_CASES=1` since MR label `BUILD_AND_TEST_ALL_APPS` is set')
        else:
            description = os.getenv('CI_MERGE_REQUEST_DESCRIPTION', '')
            if description:
                pattern = r'^## Dynamic Pipeline Configuration(?:[^`]*?)```(?:\w+)(.*?)```'
                result = re.search(pattern, description, re.DOTALL | re.MULTILINE)
                if result:
                    data = yaml.safe_load(result.group(1))
                    if 'Test Case Filters' in data:
                        res['IDF_CI_SELECT_BY_FILTER_EXPR'] = ' or '.join(data.get('Test Case Filters'))
                        logger.info(
                            f'Setting `IDF_CI_SELECT_BY_FILTER_EXPR={res["IDF_CI_SELECT_BY_FILTER_EXPR"]}` '
                            f'based on MR description "Test Case Filters"'
                        )
                        res['IDF_CI_IS_DEBUG_PIPELINE'] = '1'
                        logger.info('Setting `IDF_CI_IS_DEBUG_PIPELINE=1` based on MR description "Test Case Filters"')

    return res
