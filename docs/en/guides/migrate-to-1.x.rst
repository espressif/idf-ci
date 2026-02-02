###############################
 Migration Guide to idf-ci 1.x
###############################

This guide outlines the breaking changes introduced in idf-ci 1.0.

*********************************
 Configuration Structure Changes
*********************************

The artifact configuration structure has been reorganized for better clarity and flexibility:

**Before (0.x):**

.. code-block:: toml

    [gitlab.artifacts]
    s3_file_mode = "zip"

    [gitlab.artifacts.s3_zip.flash]
    bucket = "idf-artifacts"
    zip_basedir_pattern = "**/build*/"
    zip_file_patterns = [
        "bootloader/*.bin",
        "*.bin",
    ]

**After (1.x):**

.. code-block:: toml

    [gitlab.artifacts.s3]
    enable = true

    # by default zip_first is true, so the files will be zipped before upload
    [gitlab.artifacts.s3.configs.flash]
    bucket = "idf-artifacts"
    base_dir_pattern = "**/build*/"
    file_patterns = [
        "bootloader/*.bin",
        "*.bin",
    ]

    [gitlab.artifacts.s3.configs.metrics]
    bucket = "idf-artifacts"
    zip_first = false
    file_patterns = [
        "**/size*.json"
    ]

Key Changes:

- ``s3`` and ``s3_zip`` configurations merged into ``s3.configs``

  - Moved ``gitlab.artifacts.s3.[key]`` to ``gitlab.artifacts.s3.configs.[key]``
  - Moved ``gitlab.artifacts.s3_zip.[key]`` to ``gitlab.artifacts.s3.configs.[key]``

- Renamed ``gitlab.artifacts.build_job_filepatterns`` to ``gitlab.artifacts.native.build_job_filepatterns``
- Renmaed ``gitlab.artifacts.test_job_filepatterns`` to ``gitlab.artifacts.native.test_job_filepatterns``
- New options: ``is_public``, ``zip_first`` for conditional artifact types
- Mixed artifact type upload/download is now supported

***********************
 Environment Variables
***********************

Removed:

- ``IDF_S3_BUCKET`` (bucket now specified per artifact type in config)
