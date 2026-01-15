######################
 idf-ci Configuration
######################

This guide explains how to inspect and override idf-ci settings. For command syntax and options, see :doc:`../references/cli-commands`.

*********************************
 Check the current configuration
*********************************

Use the ``config`` command group to inspect the effective configuration after all overrides are applied.

Show a resolved value and its source (default, config file, or CLI override):

.. code-block:: bash

    idf-ci config show gitlab.project_name

*************************
 Understand a config key
*************************

Use ``explain`` to see a key's type, default, and available subkeys:

.. code-block:: bash

    idf-ci config explain gitlab

Use dot-separated paths for nested keys:

.. code-block:: bash

    idf-ci config explain gitlab.build_pipeline.runs_per_job

******************************
 Put overrides in a TOML file
******************************

Create or edit ``.idf_ci.toml`` at your repo root:

.. code-block:: toml

    [gitlab.build_pipeline]
    runs_per_job = 10
    workflow_name = "A workflow name"

You can also generate a starter file with:

.. code-block:: bash

    idf-ci init

If the file lives elsewhere, point to it with ``--config-file``.

******************************
 Override values from the CLI
******************************

Use dot-path assignments with ``--config``. If there are spaces around ``=``, quote the whole assignment. Values use Python literal syntax (``10``, ``True``, ``"str"``, ``{...}``, ``[...]``).

.. code-block:: bash

    # with spaces (quote it)
    idf-ci --config 'gitlab.build_pipeline.runs_per_job = 10' ...

    # without spaces
    idf-ci --config 'gitlab.build_pipeline.workflow_name="A workflow name"' ...

    # multiple overrides
    idf-ci \
      --config 'gitlab.build_pipeline.runs_per_job=10' \
      --config 'gitlab.build_pipeline.workflow_name="A workflow name"' \
      ...

***********************************
 Understand how config is resolved
***********************************

Configuration resolution (highest to lowest priority):

- CLI overrides (``--config``)
- Config file (``.idf_ci.toml`` or ``--config-file``)
- Defaults

Config file discovery searches upward from the current working directory for ``.idf_ci.toml``. Use ``--config-file`` to bypass discovery and point to an explicit file.

******************************
 Where to find default values
******************************

See the reference: :doc:`../references/ci-config-file` (all fields and defaults). You can expand "Show JSON schema" to see the full structure.
