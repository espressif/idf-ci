Build Commands
==============

The IDF CI tool provides commands for building applications. The ``idf-ci build`` commands allow you to build applications and manage build configurations.

Build Commands
--------------

Run Build
~~~~~~~~~

To execute the build process for applications, use the ``run`` command:

.. code-block:: bash

    idf-ci build run [OPTIONS]

This command builds applications based on the specified options and paths.

Options:

- ``--paths PATHS`` - Paths to process
- ``--target TARGET`` - Target to be processed (default: all)
- ``--parallel-count COUNT`` - Number of parallel builds
- ``--parallel-index INDEX`` - Index of parallel build (1-based)
- ``--modified-files FILES`` - List of modified files
- ``--only-test-related`` - Run build only for test-related apps
- ``--only-non-test-related`` - Run build only for non-test-related apps
- ``--dry-run`` - Run build in dry-run mode
- ``--marker-expr EXPR`` - Pytest marker expression
- ``--filter-expr EXPR`` - Pytest filter expression

Examples:

.. code-block:: bash

    # Build all applications
    idf-ci build run

    # Build specific applications
    idf-ci build run --paths /path/to/app1 /path/to/app2

    # Build for a specific target
    idf-ci build run --target esp32

    # Build only test-related applications
    idf-ci build run --only-test-related

    # Build with parallel processing
    idf-ci build run --parallel-count 4 --parallel-index 1

Initialize Build Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To create a build configuration file with default values, use the ``init`` command:

.. code-block:: bash

    idf-ci build init [OPTIONS]

Options:

- ``--path PATH`` - Path to create the config file

Example:

.. code-block:: bash

    # Create build configuration file in current directory
    idf-ci build init

    # Create build configuration file in specific directory
    idf-ci build init --path /path/to/config
