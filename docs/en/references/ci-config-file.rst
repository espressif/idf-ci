CI Config File
==============

By default, it is located at ``.idf_ci.toml`` in the root of the project.

Default Settings
----------------

.. literalinclude:: ../../../idf_ci/templates/.idf_ci.toml
    :language: toml

Configuration Options
---------------------

The following sections describe all configuration options available in the CI config file.

.. autopydantic_settings:: idf_ci.settings.CiSettings

.. autopydantic_settings:: idf_ci.settings.GitlabSettings
