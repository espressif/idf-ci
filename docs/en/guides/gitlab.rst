########
 GitLab
########

***********
 Artifacts
***********

We have several types of artifacts:

-  debug
-  flash
-  metrics

When set all required s3 env vars, the artifacts with ``debug``, ``flash``, ``metrics`` will be uploaded to s3 bucket, instead of internal gitlab.

You can override the default file patterns in your project's ``.idf_ci.toml`` file.

Artifact Management Commands
============================

The IDF CI tool provides commands for managing artifacts in GitLab pipelines. The ``idf-ci gitlab`` commands allow you to download artifacts from a GitLab pipeline or upload artifacts to S3 storage associated with a GitLab project.

These commands are especially useful when:

-  You need to access build artifacts from a CI pipeline
-  You want to share artifacts between CI jobs
-  You need to download debug information for troubleshooting
-  You want to use build outputs from a CI pipeline for local testing

Prerequisites
-------------

To use these commands, you need:

#. GitLab API access:

   -  ``GITLAB_HTTPS_SERVER`` - GitLab server URL (default: https://gitlab.com)
   -  ``GITLAB_ACCESS_TOKEN`` - GitLab API access token

#. S3 storage configuration (only required for S3 features):

   -  ``IDF_S3_SERVER`` - S3 server URL
   -  ``IDF_S3_BUCKET`` - S3 bucket name (default: idf-artifacts)
   -  ``IDF_S3_ACCESS_KEY`` - S3 access key
   -  ``IDF_S3_SECRET_KEY`` - S3 secret key
   -  ``IDF_PATH`` - Path to the ESP-IDF installation

These variables can be set in your environment or configured in your ``.idf_ci.toml`` configuration file.

Downloading Artifacts
---------------------

To download artifacts from a GitLab pipeline, use the ``download-artifacts`` command:

.. code:: bash

   idf-ci gitlab download-artifacts [OPTIONS] [FOLDER]

This command downloads artifacts from either GitLab's built-in storage or S3 storage, depending on the configuration. Only the artifacts under the specified folder will be downloaded in-place. If no folder is specified, the artifacts under the current directory will be downloaded.

Options:

-  ``--type [debug|flash|metrics]`` - Type of artifacts to download (if not specified, downloads all types)
-  ``--commit-sha COMMIT_SHA`` - Commit SHA to download artifacts from
-  ``--branch BRANCH`` - Git branch to get the latest pipeline from

Examples:

.. code:: bash

   # Download all artifacts from a specific commit under the current directory
   idf-ci gitlab download-artifacts --commit-sha abc123

   # Download only flash artifacts from a specific commit under a specific folder
   idf-ci gitlab download-artifacts --type flash --commit-sha abc123 /path/to/folder

   # Download all artifacts from latest pipeline of current branch
   idf-ci gitlab download-artifacts

   # Download debug artifacts from latest pipeline of a specific branch
   idf-ci gitlab download-artifacts --type debug --branch feature/new-feature

Artifact Types Details
----------------------

The following artifact types are supported:

#. **Flash artifacts** (``--type flash``):

   -  Bootloader binaries (``**/build*/bootloader/*.bin``)
   -  Application binaries (``**/build*/*.bin``)
   -  Partition table binaries (``**/build*/partition_table/*.bin``)
   -  Flasher arguments (``**/build*/flasher_args.json``, ``**/build*/flash_project_args``)
   -  Configuration files (``**/build*/config/sdkconfig.json``, ``**/build*/sdkconfig``)
   -  Project information (``**/build*/project_description.json``)

#. **Debug artifacts** (``--type debug``):

   -  Map files (``**/build*/bootloader/*.map``, ``**/build*/*.map``)
   -  ELF files (``**/build*/bootloader/*.elf``, ``**/build*/*.elf``)
   -  Build logs (``**/build*/build.log``)

#. **Metrics artifacts** (``--type metrics``):

   -  Size information (``**/build*/size.json``)

Uploading Artifacts
-------------------

To upload artifacts to S3 storage, use the ``upload-artifacts`` command:

.. code:: bash

   idf-ci gitlab upload-artifacts [OPTIONS] [FOLDER]

This command uploads artifacts to S3 storage only. GitLab's built-in storage is not supported. The commit SHA is required to identify where to store the artifacts. Only the artifacts under the specified folder will be downloaded in-place. If no folder is specified, the artifacts under the current directory will be downloaded.

Options:

-  ``--type [debug|flash|metrics]`` - Type of artifacts to upload
-  ``--commit-sha COMMIT_SHA`` - Commit SHA to upload artifacts to (required)

Example:

.. code:: bash

   # Upload all debug artifacts from current directory to a specific commit
   idf-ci gitlab upload-artifacts --type debug --commit-sha abc123

   # Upload flash artifacts from a specific directory
   idf-ci gitlab upload-artifacts --type flash --commit-sha abc123 /path/to/build

Implementation Details
----------------------

Internally, the artifact management commands use the ``ArtifactManager`` class, which handles:

#. GitLab API operations (pipeline, merge request queries)
#. S3 storage operations (artifact upload/download)
#. Fallback to GitLab storage when S3 is not configured

The artifacts are stored with a prefix that includes the project ID and commit SHA: ``{project_namespace}/{project_name}/{commit_sha}/path/to/artifact``

This structure ensures artifacts are properly organized and can be easily located by commit.

*************
 CI Pipeline
*************

Usually in each CI pipeline we have two stages:

-  build
-  test

``build`` stage is responsible for building the test apps, which compiled the binaries required by running the tests, and target test is

``test`` stage is responsible for running the tests.
