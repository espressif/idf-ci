###############
 Test Commands
###############

Reference for the ``idf-ci test`` command group, which collects test cases and manages ``pytest.ini``.

**************
 test collect
**************

To collect and process pytest cases, use the ``collect`` command:

.. code-block:: bash

    idf-ci test collect [OPTIONS] [PATHS]

This command collects pytest cases from the specified paths (defaults to the current directory) and processes them according to the options.

Options:

- ``--target TARGET`` - Target to process (default: all)
- ``--marker-expr EXPR`` - Pytest marker expression
- ``--filter-expr EXPR`` - Pytest filter expression
- ``--format FORMAT`` - Output format (raw or github, default: raw)
- ``--output OUTPUT`` - Output destination (defaults to stdout)

Examples:

.. code-block:: bash

    # Collect all test cases
    idf-ci test collect

    # Collect test cases from specific paths
    idf-ci test collect /path/to/test1 /path/to/test2

    # Collect test cases for a specific target
    idf-ci test collect --target esp32

    # Collect test cases with specific markers
    idf-ci test collect --marker-expr "not slow"

    # Output in GitHub format
    idf-ci test collect --format github

    # Save output to file
    idf-ci test collect --output test_cases.txt

***********
 test init
***********

To create a test configuration file with default values (``pytest.ini``), use the ``init`` command:

.. code-block:: bash

    idf-ci test init [OPTIONS]

Options:

- ``--path PATH`` - Path to create the config file

Examples:

.. code-block:: bash

    # Create test configuration file in current directory
    idf-ci test init

    # Create test configuration file in specific directory
    idf-ci test init --path /path/to/config
