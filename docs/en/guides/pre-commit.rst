##################
 Pre-commit Hooks
##################

The ``idf-ci`` package provides `pre-commit <https://pre-commit.com/>`_ hooks to catch critical issues before code is committed.

*******
 Setup
*******

Add the following to your ``.pre-commit-config.yaml``:

.. code-block:: yaml

    repos:
      - repo: https://github.com/espressif/idf-ci
        rev: v0.7.0  # Use the latest version
        hooks:
          - id: check-tests-missing-config

Run manually:

.. code-block:: bash

    pre-commit run check-tests-missing-config

*****************
 Available Hooks
*****************

check-tests-missing-config
==========================

Validates that test cases reference existing sdkconfig files.

What It Checks
--------------

The hook scans modified files, collects test cases from their parent directories, and verifies that each test case's ``config`` parameter corresponds to an actual sdkconfig file in the project.

For example, if a test case specifies ``release`` config, the hook checks that a file like ``sdkconfig.ci.release`` exists.

When It Runs
------------

- **pre-commit**: Before each commit
- **pre-merge-commit**: Before merge commits
- **manual**: When explicitly invoked

Example Output
--------------

When the hook detects missing sdkconfig files, it produces output like:

.. code-block:: text

    Error: Test cases requiring missing sdkconfig files.

    Please make sure the following sdkconfig files exist or update config name in test case parameters.
    For more information, refer to documentation: https://docs.espressif.com/projects/idf-build-apps/en/latest/explanations/config_rules.html

    ./foo
            Sdkconfig file "release" is missing for test cases:
                    - test_case_1
                    - test_case_2

How to Fix
----------

- **Create the missing sdkconfig file**: Ensure that the sdkconfig file referenced in the test case exists in the project. If it doesn't, create it.
- **Update the test case**: Change the config name in the test case to match an existing sdkconfig file.
- **Use default config**: Remove the config parameter if no special configuration is needed.

For details on sdkconfig file naming conventions, see the ``idf-build-apps`` `config rules documentation <https://docs.espressif.com/projects/idf-build-apps/en/latest/explanations/config_rules.html>`_.
