CLI Overview
============

The ``idf-ci`` tool provides a comprehensive command-line interface for managing builds, tests, and GitLab CI/CD operations. This document provides an overview of the CLI structure, global options, and available command groups.

Basic Usage
-----------

The basic syntax for using the IDF CI tool is:

.. code-block:: bash

    idf-ci [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGUMENTS]

Getting Help
------------

You can get help for any command using the ``--help`` or ``-h`` option:

.. code-block:: bash

    # Get general help
    idf-ci --help

    # Get help for a specific command group
    idf-ci build --help

    # Get help for a specific command
    idf-ci build run --help

Global Options
--------------

These options are available for all commands and affect the overall behavior of the tool:

``--config-file, -c PATH``
    Path to the idf-ci config file. Use this to specify a custom configuration file location instead of the default ``.idf_ci.toml``.

    .. code-block:: bash

        idf-ci --config-file /path/to/custom.toml build run

``--debug``
    Enable debug logging. This provides detailed output for troubleshooting.

    .. code-block:: bash

        idf-ci --debug gitlab download_artifacts

Global Commands
---------------

``init``
    Create a default ``.idf_ci.toml`` configuration file in the current directory or specified path.

    .. code-block:: bash

        # Create config file in current directory
        idf-ci init

        # Create config file in specific location
        idf-ci init --path /path/to/project

``completions``
    Display instructions for enabling shell autocompletion for the idf-ci command. Supports Bash, Zsh, and Fish shells.

    .. code-block:: bash

        idf-ci completions

Shell Completion
----------------

The tool supports shell autocompletion for Bash, Zsh, and Fish. Use ``idf-ci completions`` to get setup instructions for your shell.

Command Groups
--------------

For detailed information about specific command groups:

.. toctree::
    :maxdepth: 1
    :caption: Command Groups
    :glob:

    cli_group_cmds/*
