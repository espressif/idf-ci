Test Commands
=============

The IDF CI tool provides commands for managing and running tests. The ``idf-ci test`` commands allow you to collect test cases and manage test configurations.

Test Commands
-------------

Collect Test Cases
~~~~~~~~~~~~~~~~~~

To collect and process pytest cases, use the ``collect`` command:

.. code-block:: bash

    idf-ci test collect [OPTIONS] [PATHS]

This command collects pytest cases from the specified paths and processes them according to the options.

Options:

- ``--target TARGET`` - Target to be processed (default: all)
- ``--marker-expr EXPR`` - Pytest marker expression
- ``--filter-expr EXPR`` - Pytest filter expression
- ``--format FORMAT`` - Output format (raw or github, default: raw)
- ``--output OUTPUT`` - Output destination (stdout if not provided)

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

Initialize Test Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To create a test configuration file with default values, use the ``init`` command:

.. code-block:: bash

    idf-ci test init [OPTIONS]

Options:

- ``--path PATH`` - Path to create the config file

Example:

.. code-block:: bash

    # Create test configuration file in current directory
    idf-ci test init

    # Create test configuration file in specific directory
    idf-ci test init --path /path/to/config
