#################
 GitLab Commands
#################

Reference for the ``idf-ci gitlab`` command group.

***********
 Artifacts
***********

The system supports two types of artifact storage: GitLab native artifacts and S3 artifacts. Both can be enabled simultaneously based on your configuration.

**GitLab Native Artifacts**

GitLab native artifacts are enabled by default and use GitLab's built-in storage system. These artifacts are automatically uploaded to GitLab's servers as part of CI/CD jobs.

**S3 Artifacts**

When S3 credentials are configured and ``gitlab.artifacts.s3.enable`` is ``true``, artifacts can also be stored in S3. Each S3 artifact configuration can specify whether to upload as zip files (``zip_first: true``) or individual files (``zip_first: false``).

The following artifact types are enabled by default:

- debug
- flash

You can override default file patterns for both GitLab native and S3 artifacts in ``.idf_ci.toml``. See :doc:`../../references/ci-config-file` for the full schema.

Artifact Pattern Overrides
==========================

Customize which files are uploaded by editing ``.idf_ci.toml``. You can configure both GitLab native artifacts and S3 artifacts.

**S3 Artifact Configuration**

For S3 artifacts, you can specify whether to upload as zip files or individual files using the ``zip_first`` option:

.. code-block:: toml

    [gitlab.artifacts.s3]
    enable = true

    [gitlab.artifacts.s3.configs.flash]
    bucket = "idf-artifacts"
    base_dir_pattern = "**/build*/"
    zip_first = true  # Upload as zip files
    patterns = []  # this overrides the default patterns to empty list

    [gitlab.artifacts.s3.configs.custom_group]
    bucket = "custom-bucket"
    base_dir_pattern = "**/build*/"
    zip_first = false  # Upload individual files instead of zip (default)
    patterns = [
        "custom/*.log",
        "custom/*.txt"
    ]
    if_clause = 'ENV_VAR_FOO == "foo"'

**GitLab Native Artifact Configuration**

GitLab native artifacts are configured separately and always upload individual files matching the specified patterns:

.. code-block:: toml

    [gitlab.artifacts.native]
    enable = true
    build_job_filepatterns = [
        "**/build*/bootloader/*.bin",
        "**/build*/*.bin",
        # ... other patterns
    ]

Artifact Commands
=================

Use these commands to download artifacts from pipelines or upload artifacts to S3 storage associated with a GitLab project.

Prerequisites
-------------

To use these commands, configure:

1. GitLab API access:

   - ``GITLAB_HTTPS_SERVER`` - GitLab server URL (default: https://gitlab.com)
   - ``GITLAB_ACCESS_TOKEN`` - GitLab API access token

2. S3 storage (only required for S3 features):

   - ``IDF_S3_SERVER`` - S3 server URL
   - ``IDF_S3_ACCESS_KEY`` - S3 access key
   - ``IDF_S3_SECRET_KEY`` - S3 secret key
   - ``IDF_PATH`` - Path to the ESP-IDF installation

You can set these in the environment or in ``.idf_ci.toml``. For the full list of GitLab-related variables, see :doc:`../../references/gitlab-env-vars`.

Pipeline Variables
------------------

To output dynamic pipeline variables, use ``pipeline-variables``:

.. code-block:: bash

    idf-ci gitlab pipeline-variables

This command analyzes the current GitLab pipeline environment and outputs variables as ``KEY=VALUE`` for use with GitLab's export feature.

For more details about the generated variables, please refer to the API documentation.

Build Child Pipeline
--------------------

Generate a build child pipeline YAML file. If ``YAML_OUTPUT`` is omitted, the YAML is written to stdout:

.. code-block:: bash

    idf-ci gitlab build-child-pipeline [OPTIONS] [YAML_OUTPUT]

Options:

- ``--paths PATHS`` - Paths to process
- ``--modified-files MODIFIED_FILES`` - List of modified files
- ``--compare-manifest-sha-filepath PATH`` - Path to the recorded manifest sha file (default: .manifest_sha)

Test Child Pipeline
-------------------

Generate a test child pipeline YAML file. If ``YAML_OUTPUT`` is omitted, the YAML is written to stdout:

.. code-block:: bash

    idf-ci gitlab test-child-pipeline [YAML_OUTPUT]

Download S3 Artifacts
---------------------

Download artifacts from S3 storage with ``download-artifacts``:

.. code-block:: bash

    idf-ci gitlab download-artifacts [OPTIONS] [FOLDER]

Artifacts are downloaded from S3 when credentials are available. If you provide a folder, only artifacts under that folder are downloaded into it. If no folder is specified, artifacts under the current directory are downloaded into the current directory. When S3 access is not available, the command can download from presigned URLs (via ``--presigned-json`` or ``--pipeline-id``).

There are two main use cases for downloading artifacts:

With S3 Access
^^^^^^^^^^^^^^

With direct S3 credentials, you can download artifacts from S3 using a commit SHA or branch.

Supported options:

- ``--type [...]`` - Type of artifacts to download (if not specified, downloads all types)
- ``--commit-sha COMMIT_SHA`` - Commit SHA to download artifacts from
- ``--branch BRANCH`` - Git branch to get the latest pipeline from

Examples:

.. code-block:: bash

    # Download all artifacts from a specific commit under the current directory
    idf-ci gitlab download-artifacts --commit-sha abc123

    # Download only flash artifacts from a specific commit under a specific folder
    idf-ci gitlab download-artifacts --type flash --commit-sha abc123 /path/to/folder

    # Download all artifacts from latest pipeline of current branch
    idf-ci gitlab download-artifacts

    # Download debug artifacts from latest pipeline of a specific branch
    idf-ci gitlab download-artifacts --type debug --branch feature/new-feature

Without S3 Access
^^^^^^^^^^^^^^^^^

Without S3 credentials but with GitLab access, you can download artifacts using ``--presigned-json`` or ``--pipeline-id``. With ``--pipeline-id``, the system first fetches presigned JSON using your GitLab account, then uses presigned URLs to download the artifacts.

The ``--pipeline-id`` option requires ``gitlab.build_pipeline.presigned_json_job_name`` to be configured so the presigned JSON artifact can be located.

Supported options:

- ``--type [...]`` - Type of artifacts to download (if not specified, downloads all types)
- ``--presigned-json PATH`` - Path to a presigned.json file
- ``--pipeline-id PIPELINE_ID`` - Main pipeline ID to download artifacts from

Examples:

.. code-block:: bash

    # Download all artifacts from a specific pipeline under the current directory
    idf-ci gitlab download-artifacts --pipeline-id 12345

    # Download only debug artifacts from a specific pipeline under a specific folder
    idf-ci gitlab download-artifacts --pipeline-id 12345 --type debug /path/to/folder

    # Download flash artifacts from a specific pipeline
    idf-ci gitlab download-artifacts --pipeline-id 12345 --type flash

Artifact Type Details
---------------------

Artifact types can be configured for both GitLab native storage and S3 storage. By default, the following types are configured:

**GitLab Native Artifacts**

GitLab native artifacts use file patterns defined in ``gitlab.artifacts.native.build_job_filepatterns`` and ``gitlab.artifacts.native.test_job_filepatterns``. These patterns directly specify which files to upload to GitLab's storage.

**S3 Artifacts**

S3 artifact types are defined under ``gitlab.artifacts.s3.configs``. By default, these are configured with ``base_dir_pattern = "**/build*/"``. Depending on the ``zip_first`` setting:

- If ``zip_first = true``: Each matching base directory generates a ``<artifact_type>.zip`` containing the matching files
- If ``zip_first = false`` (default): Individual files are uploaded directly to S3 without zipping

1. **Flash artifacts** (``--type flash``):

   - Bootloader binaries (``bootloader/*.bin``)
   - Application binaries (``*.bin``)
   - Partition table binaries (``partition_table/*.bin``)
   - Flasher arguments (``flasher_args.json``, ``flash_project_args``)
   - Configuration files (``config/sdkconfig.json``, ``sdkconfig``)
   - Project information (``project_description.json``)

2. **Debug artifacts** (``--type debug``):

   - Map files (``bootloader/*.map``, ``*.map``)
   - ELF files (``bootloader/*.elf``, ``*.elf``)
   - Build logs (``build.log``)

Upload S3 Artifacts
-------------------

Upload artifacts to S3 storage with ``upload-artifacts``:

.. code-block:: bash

    idf-ci gitlab upload-artifacts [OPTIONS] [FOLDER]

This command uploads to S3 only; GitLab built-in storage is not supported. If the commit SHA is omitted, it is resolved from ``PIPELINE_COMMIT_SHA`` or the latest commit on the selected branch. If you provide a folder, only artifacts under that folder are uploaded. If no folder is specified, artifacts under the current directory are uploaded.

Options:

- ``--type [debug|flash]`` - Type of artifacts to upload
- ``--commit-sha COMMIT_SHA`` - Commit SHA to upload artifacts to
- ``--branch BRANCH`` - Git branch to use (if not provided, will use current git branch)

Example:

.. code-block:: bash

    # Upload all debug artifacts from current directory to a specific commit
    idf-ci gitlab upload-artifacts --type debug --commit-sha abc123

    # Upload flash artifacts from a specific directory
    idf-ci gitlab upload-artifacts --type flash --commit-sha abc123 /path/to/build

Generate Presigned URLs
-----------------------

Generate presigned URLs for S3 artifacts with ``generate-presigned-json``:

.. code-block:: bash

    idf-ci gitlab generate-presigned-json [OPTIONS] [FOLDER]

This command generates presigned URLs for artifacts that would be uploaded to S3 storage. The URLs can be used to download the artifacts directly from S3.

Options:

- ``--commit-sha COMMIT_SHA`` - Commit SHA to generate presigned URLs for
- ``--branch BRANCH`` - Git branch to use (if not provided, will use current git branch)
- ``--type [debug|flash]`` - Type of artifacts to generate URLs for
- ``--expire-in-days DAYS`` - Expiration time in days for the presigned URLs (default: 4 days)

Example:

.. code-block:: bash

    # Generate presigned URLs for debug artifacts
    idf-ci gitlab generate-presigned-json --type debug --commit-sha abc123

Download Known Failure Cases
----------------------------

Download a known failure cases file from S3 with ``download-known-failure-cases-file``:

.. code-block:: bash

    idf-ci gitlab download-known-failure-cases-file FILENAME

S3 storage must be configured for this command to work.

Implementation Details
----------------------

Internally, the artifact commands use the ``ArtifactManager`` class, which handles:

1. GitLab API operations (pipeline, merge request queries)
2. S3 storage operations (artifact upload/download)
3. Fallback to presigned URLs when S3 access is unavailable or fails

Artifacts are stored with a prefix that includes the project ID and commit SHA: ``{project_namespace}/{project_name}/{commit_sha}/path/to/artifact``

This structure ensures artifacts are properly organized and can be easily located by commit.

*************
 CI Pipeline
*************

A typical CI pipeline has two stages:

- build
- test

The ``build`` stage builds test apps and the binaries required for tests.

The ``test`` stage runs the tests.
