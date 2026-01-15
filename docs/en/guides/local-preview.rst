#############################
 Preview CI Behavior Locally
#############################

This guide shows how to preview CI behavior locally without running a full pipeline.

*************
 Build Stage
*************

The build stage builds project binaries and test binaries. It uses settings from ``.idf_build_apps.toml``; see :doc:`../references/build-config-file`.

We split the build stage into two parts:

- Test-related build: builds test binaries to be executed later in the test stage.
- Non-test-related build: builds project binaries for compilation checks.

Preview the build stage locally:

.. code-block:: bash

    idf-ci build run --dry-run

Preview only the test-related build:

.. code-block:: bash

    idf-ci build run --dry-run --only-test-related

Preview only the non-test-related build:

.. code-block:: bash

    idf-ci build run --dry-run --only-non-test-related

************
 Test Stage
************

The test stage runs pytest. Because idf-ci integrates as a pytest plugin, you can use standard pytest options to inspect what would run. Pytest settings live in ``pytest.ini``; see :doc:`../references/test-config-file`.

Preview test collection:

.. code-block:: bash

    pytest --collect-only

Filter by test name with ``-k``:

.. code-block:: bash

    pytest --collect-only -k test_func_name

Filter by markers with ``-m``:

.. code-block:: bash

    pytest --collect-only -m "not host_test"

For multi-DUT tests, pass a comma-separated list of targets:

.. code-block:: bash

    pytest --collect-only --target esp32,esp32s2

Increase log verbosity:

.. code-block:: bash

    pytest --collect-only --log-cli-level DEBUG

The default log level is ``WARNING``. Python logging levels are ``DEBUG < INFO < WARNING < ERROR < CRITICAL``. Only messages at or above the selected level are shown.
