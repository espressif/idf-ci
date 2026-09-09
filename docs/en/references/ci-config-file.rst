################
 CI Config File
################

This page is a reference for available keys and their defaults. For step-by-step usage and examples, see :doc:`../guides/idf-ci-configuration`. To generate a starter file, run ``idf-ci init``.

******************
 Default Settings
******************

.. literalinclude:: ../../../idf_ci/templates/.idf_ci.toml
    :language: toml

***********************
 Configuration Options
***********************

The following sections describe all configuration options in the CI config file.

.. autopydantic_settings:: idf_ci.settings.CiSettings

.. autopydantic_settings:: idf_ci.settings.GitlabSettings

.. autopydantic_settings:: idf_ci.settings.ArtifactSettings

.. autopydantic_settings:: idf_ci.settings.ArtifactSettingsS3

.. autopydantic_settings:: idf_ci.settings.ArtifactSettingsNative

.. autopydantic_settings:: idf_ci.settings.S3ArtifactConfig

.. autopydantic_settings:: idf_ci.settings.BuildPipelineSettings

.. autopydantic_settings:: idf_ci.settings.TestPipelineSettings
