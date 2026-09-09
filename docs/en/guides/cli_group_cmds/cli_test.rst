###############
 Test Commands
###############

Reference for the ``idf-ci test`` command group, which collects test cases and manages ``pytest.ini``.

**************
 test collect
**************

Collect and process pytest cases based on target, markers, and paths:

.. code-block:: bash

    idf-ci test collect [OPTIONS] [PATHS...]

If ``PATHS`` are not specified, tests are collected from the current directory.

Options:

- ``-t, --target TARGET`` - Target chip to filter by, or ``all`` for all targets (default: ``all``)
- ``-m, --marker-expr EXPR`` - Pytest marker expression (e.g. ``"not slow"``, ``"qemu"``)
- ``-k, --filter-expr EXPR`` - Pytest filter expression matching test names
- ``--format [raw|github]`` - Output format: ``raw`` (space-separated test node IDs) or ``github`` (GitHub Actions workflow outputs; default: ``raw``)
- ``-o, --output OUTPUT`` - File path to save output to (default: print to stdout)

Emulator Markers
================

Cases marked with an emulator marker (such as ``qemu`` or ``espemu``):

- Automatically configure pytest-embedded services (``idf,qemu`` or ``idf,espemu``).
- Run as host tests, so they are kept separate from target hardware test jobs.
- Include the emulator name in their case ID (for example, ``esp32c3_espemu.default.test_foo``) so that emulator results stay distinct from real-target runs.

Examples:

.. code-block:: bash

    # Collect all test cases in current directory
    idf-ci test collect

    # Collect test cases from specific paths
    idf-ci test collect path/to/tests1 path/to/tests2

    # Collect test cases for a specific target
    idf-ci test collect -t esp32

    # Collect test cases with marker filter
    idf-ci test collect -m "not host_test"

    # Collect test cases running on QEMU
    idf-ci test collect -m "qemu"

    # Format output for GitHub Actions
    idf-ci test collect --format github

    # Save collected node IDs to a file
    idf-ci test collect -o test_nodes.txt

***********
 test init
***********

Create a starter test configuration file (``pytest.ini``) with default settings:

.. code-block:: bash

    idf-ci test init [OPTIONS]

Options:

- ``--path PATH`` - Directory or file path where ``pytest.ini`` is created

Examples:

.. code-block:: bash

    # Create pytest.ini in current directory
    idf-ci test init

    # Create pytest.ini in a specific directory
    idf-ci test init --path /path/to/project
