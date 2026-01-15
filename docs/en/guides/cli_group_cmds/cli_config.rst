#################
 Config Commands
#################

Reference for the ``idf-ci config`` command group. For configuration resolution rules and override precedence, see :doc:`../../guides/idf-ci-configuration`.

*************
 config show
*************

The ``show`` command prints the value for a dot-path key and reports where that value came from. It also prints the config file path used (if any).

.. code-block:: bash

    idf-ci config show gitlab.build_pipeline.runs_per_job

Expected output includes:

- Config file path (or ``<not found>`` if discovery failed)
- Source (CLI override, config file, or default)
- Value rendered as TOML

****************
 config explain
****************

The ``explain`` command reports the type, default, and description for a key. If the key points to a section, it lists available subkeys.

.. code-block:: bash

    idf-ci config explain gitlab.build_pipeline

For leaf keys, ``explain`` prints the default value in TOML format. If the key accepts a fixed set of values, it also lists the choices.

Use dot-path syntax for nested keys, for example ``gitlab.build_pipeline.runs_per_job``.
