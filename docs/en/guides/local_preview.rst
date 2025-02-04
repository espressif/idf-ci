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

   idf-ci test run --target <target> --dry-run

For example, to preview the behavior of the test stage for the ``esp32`` target, you can run the following command:

.. code:: bash

   idf-ci test run --target esp32 --dry-run

For multi-dut tests, you can pass with comma separated values:

.. code:: bash

   idf-ci test run --target esp32,esp32s2 --dry-run
