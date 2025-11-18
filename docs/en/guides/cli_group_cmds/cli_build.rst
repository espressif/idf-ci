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
- ``--build-system SYSTEM`` - Filter the apps by build system. Can be "cmake", "make" or a custom App class path (default: cmake)
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

    # Build applications using make build system
    idf-ci build run --build-system make

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

Collect Applications
~~~~~~~~~~~~~~~~~~~~

This command collects all applications, corresponding test cases and outputs the result in JSON format.

.. code-block:: bash

    idf-ci build collect [OPTIONS]

Options:

- ``--paths PATHS`` - Paths to search for applications. If not provided, current directory is used
- ``--output OUTPUT`` - Output destination. If not provided, stdout is used

Output format:

.. code-block:: json

    {
        "paths": {
            "app_path_1": [
                {
                    "target": "esp32",
                    "sdkconfig": "release",
                    "build_status": "should be built",
                    "build_comment": "",
                    "test_cases": [
                        "test_case_1",
                        "test_case_2"
                    ]
                }
            ]
        }
    }

Examples:

.. code-block:: bash

    # Collect applications in current directory
    idf-ci build collect

    # Collect applications in specified directories
    idf-ci build collect --paths /path/to/dir1 /path/to/dir2

    # Collect applications and output to a file
    idf-ci build collect --output /path/to/output.json
