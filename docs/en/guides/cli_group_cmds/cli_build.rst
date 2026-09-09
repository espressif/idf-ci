################
 Build Commands
################

Reference for the ``idf-ci build`` command group, which builds applications and manages ``.idf_build_apps.toml``.

***********
 build run
***********

Build applications based on paths and filter options:

.. code-block:: bash

    idf-ci build run [OPTIONS]

Options:

- ``-p, --paths PATHS`` - Directories to process (can pass multiple times; default: current directory)
- ``-t, --target TARGET`` - Target chip to process (default: all)
- ``--parallel-count COUNT`` - Total number of parallel build jobs
- ``--parallel-index INDEX`` - Index of this parallel build job (1-based)
- ``--modified-files FILES`` - Semicolon-separated list of modified files
- ``--only-test-related`` - Build only applications needed by tests
- ``--only-non-test-related`` - Build only applications not needed by tests
- ``--dry-run`` - Print which apps would build without compiling them
- ``--build-system SYSTEM`` - Filter apps by build system ("cmake", "make", or a custom App class)
- ``-m, --marker-expr EXPR`` - Pytest marker expression to select test apps
- ``-k, --filter-expr EXPR`` - Pytest filter expression to select test apps

Examples:

.. code-block:: bash

    # Build all applications
    idf-ci build run

    # Build applications in specific directories
    idf-ci build run -p app1 -p app2

    # Build for a specific target
    idf-ci build run --target esp32

    # Build only test-related applications
    idf-ci build run --only-test-related

    # Preview build list without compiling (dry-run)
    idf-ci build run --dry-run

    # Build using parallel jobs (job 1 of 4)
    idf-ci build run --parallel-count 4 --parallel-index 1

************
 build init
************

Create a starter build configuration file (``.idf_build_apps.toml``) with default settings:

.. code-block:: bash

    idf-ci build init [OPTIONS]

Options:

- ``--path PATH`` - Directory or file path where the config file is created

Examples:

.. code-block:: bash

    # Create .idf_build_apps.toml in current directory
    idf-ci build init

    # Create config file in a specific directory
    idf-ci build init --path /path/to/project

***************
 build collect
***************

Collect all applications and their test cases, and output the report in JSON or HTML format:

.. code-block:: bash

    idf-ci build collect [OPTIONS]

Options:

- ``-p, --paths PATHS`` - Directories to search for applications (default: current directory)
- ``-o, --output OUTPUT`` - File path to write the output to (default: print to stdout)
- ``--format [json|html]`` - Output format (default: ``json``)
- ``--include-only-enabled-apps`` - Include only enabled applications

Output format (JSON):

.. code-block:: json

    {
        "summary": {
            "total_projects": 1,
            "total_apps": 1,
            "total_test_cases": 4,
            "total_test_cases_used": 1,
            "total_test_cases_disabled": 2,
            "total_test_cases_missing_app": 1
        },
        "projects": {
            "path/to/project": {
                "apps": [
                    {
                        "target": "esp32",
                        "config": "release",
                        "build_status": "should be built",
                        "build_comment": "",
                        "test_comment": "Disabled by manifest rule: IDF_TARGET == \"esp32\" (reason: Disabled test for esp32)",
                        "test_cases": [
                            {
                                "name": "test_case_1",
                                "caseid": "esp32.release.test_case_1"
                            },
                            {
                                "name": "test_case_2",
                                "caseid": "esp32.release.test_case_2",
                                "disabled": true,
                                "disabled_by_manifest": false,
                                "disabled_by_marker": true,
                                "skip_reason": "skipped by marker"
                            },
                            {
                                "name": "test_case_3",
                                "caseid": "esp32.release.test_case_3",
                                "disabled": true,
                                "disabled_by_manifest": true,
                                "disabled_by_marker": false,
                                "test_comment": "Disabled by manifest rule: IDF_TARGET == \"esp32\" (reason: Disabled test for esp32)"
                            }
                        ]
                    }
                ],
                "missing_apps": [
                    {
                        "target": "esp32",
                        "config": "release",
                        "test_cases": [
                            {
                                "name": "test_case_4",
                                "caseid": "esp32.release.test_case_4"
                            }
                        ]
                    }
                ]
            }
        }
    }

Examples:

.. code-block:: bash

    # Collect applications in current directory
    idf-ci build collect

    # Collect applications in specified directories
    idf-ci build collect -p dir1 -p dir2

    # Save report to a JSON file
    idf-ci build collect -o output.json

    # Generate an HTML report
    idf-ci build collect --format html -o report.html

    # Collect only enabled applications
    idf-ci build collect --include-only-enabled-apps
