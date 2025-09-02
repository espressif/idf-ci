idf-ci Configuration
====================

How configuration is resolved
-----------------------------

- Precedence: **CLI overrides > TOML file > Defaults**
- Config file: ``.idf_ci.toml`` (auto-discovered upward) or pass ``--config-file``.

Override via TOML
-----------------

Create or edit ``.idf_ci.toml`` at your repo root:

.. code-block:: toml

    [gitlab.build_pipeline]
    runs_per_job = 10
    workflow_name = "A workflow name"

Override via CLI
----------------

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

Where to find default values
----------------------------

See the reference: :doc:`../references/ci-config-file` (all fields and defaults). You may expand "Show JSON schema" section to see the full structure.
