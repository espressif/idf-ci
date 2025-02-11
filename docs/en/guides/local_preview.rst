#############################
 Preview CI Behavior Locally
#############################

This guide will show you how to preview the behavior of the CI system locally.

*************
 Build Stage
*************

The build stage is the first stage of the CI system. It is responsible for building the project and running the tests.

Usually we split the build stage into two parts:

-  Test-Related Build: This part of the build stage is responsible for building the test binaries that will be run later in the test stage.
-  Non-Test-Related Build: This part of the build stage is responsible for building the project binaries that will only be compiled as a compilation check.

To preview the behavior of the build stage locally, you can run the following command:

.. code:: bash

   idf-ci build run --dry-run

Or pass ``--test-related`` to preview the behavior of the test-related build:

.. code:: bash

   idf-ci build run --dry-run --test-related

Or pass ``--non-test-related`` to preview the behavior of the non-test-related build:

.. code:: bash

   idf-ci build run --dry-run --non-test-related

Test Stage
==========

The test stage is the second stage of the CI system. It is responsible for running the tests.

To preview the behavior of the test stage locally, you can run the following command:

.. code:: bash

   pytest --collect-only

Since it's implemented as a pytest plugin, you can use all the pytest options to run the tests. For example, use -k to narrow down the tests to run:

.. code:: bash

   pytest --collect-only -k test_func_name

Or use -m to run tests with specific markers:

.. code:: bash

   pytest --collect-only -m "not host_test"

For multi-dut tests, you can pass with comma separated values:

.. code:: bash

   pytest --collect-only --target esp32,esp32s2

To enable the verbose mode, you can pass:

.. code:: bash

   pytest --collect-only --log-cli-level DEBUG

By default the log level is WARNING. In python logging, the log levels are DEBUG < INFO < WARNING < ERROR < CRITICAL. Only the logs with the level greater than or equal to the passed log level will be displayed.
