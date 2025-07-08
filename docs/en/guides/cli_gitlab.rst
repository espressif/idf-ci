GitLab Commands
===============

Artifacts
---------

We have several types of artifacts enabled by default:

- debug
- flash

When set all required s3 env vars, the artifacts with ``debug``, ``flash`` could be uploaded to s3 bucket, instead of internal gitlab.

You can override the default file patterns in your project's ``.idf_ci.toml`` file.

Customizing Artifact Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can customize which files are uploaded as artifacts by modifying your project's ``.idf_ci.toml`` file. Here's an example of how to add custom artifact patterns:

.. code-block:: toml

    [gitlab.s3.flash]
    patterns = []  # this overrides the default patterns to empty list

    [gitlab.s3.custom_group]
    bucket = "custom-bucket"
    patterns = [
        "**/build*/custom/*.log",
        "**/build*/custom/*.txt"
    ]

Artifact Management Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The IDF CI tool provides commands for managing artifacts in GitLab pipelines. The ``idf-ci gitlab`` commands allow you to download artifacts from a GitLab pipeline or upload artifacts to S3 storage associated with a GitLab project.

These commands are especially useful when:

- You need to access build artifacts from a CI pipeline
- You want to share artifacts between CI jobs
- You need to download debug information for troubleshooting
- You want to use build outputs from a CI pipeline for local testing

Prerequisites
+++++++++++++

To use these commands, you need:

1. GitLab API access:

   - ``GITLAB_HTTPS_SERVER`` - GitLab server URL (default: https://gitlab.com)
   - ``GITLAB_ACCESS_TOKEN`` - GitLab API access token

2. S3 storage configuration (only required for S3 features):

   - ``IDF_S3_SERVER`` - S3 server URL
   - ``IDF_S3_BUCKET`` - S3 bucket name (default: idf-artifacts)
   - ``IDF_S3_ACCESS_KEY`` - S3 access key
   - ``IDF_S3_SECRET_KEY`` - S3 secret key
   - ``IDF_PATH`` - Path to the ESP-IDF installation

These variables can be set in your environment or configured in your ``.idf_ci.toml`` configuration file.

Pipeline Variables
++++++++++++++++++

To output dynamic pipeline variables, use the ``pipeline-variables`` command:

.. code-block:: bash

    idf-ci gitlab pipeline-variables

This command analyzes the current GitLab pipeline environment and determines what variables to set for controlling pipeline behavior. It outputs variables in the format KEY="VALUE" for each determined variable, which can be used with GitLab's `export` feature.

For more details about the generated variables, please refer to the API documentation.

Build Child Pipeline
++++++++++++++++++++

To generate a build child pipeline YAML file, use the ``build-child-pipeline`` command:

.. code-block:: bash

    idf-ci gitlab build-child-pipeline [OPTIONS] [YAML_OUTPUT]

Options:

- ``--paths PATHS`` - Paths to process
- ``--modified-files MODIFIED_FILES`` - List of modified files
- ``--compare-manifest-sha-filepath PATH`` - Path to the recorded manifest sha file (default: .manifest_sha)

Test Child Pipeline
+++++++++++++++++++

To generate a test child pipeline YAML file, use the ``test-child-pipeline`` command:

.. code-block:: bash

    idf-ci gitlab test-child-pipeline [YAML_OUTPUT]

Downloading Artifacts
+++++++++++++++++++++

To download artifacts from a GitLab pipeline, use the ``download_artifacts`` command:

.. code-block:: bash

    idf-ci gitlab download_artifacts [OPTIONS] [FOLDER]

This command downloads artifacts from either GitLab's built-in storage or S3 storage, depending on the configuration and available access. Only the artifacts under the specified folder will be downloaded in-place. If no folder is specified, the artifacts under the current directory will be downloaded.

There are two main use cases for downloading artifacts:

**With S3 Access**
~~~~~~~~~~~~~~~~~~

When you have direct S3 credentials configured, you can download artifacts directly from S3 storage using commit SHA or branch information.

Supported Options:

- ``--type [...]`` - Type of artifacts to download (if not specified, downloads all types)
- ``--commit-sha COMMIT_SHA`` - Commit SHA to download artifacts from
- ``--branch BRANCH`` - Git branch to get the latest pipeline from

Examples:

.. code-block:: bash

    # Download all artifacts from a specific commit under the current directory
    idf-ci gitlab download_artifacts --commit-sha abc123

    # Download only flash artifacts from a specific commit under a specific folder
    idf-ci gitlab download_artifacts --type flash --commit-sha abc123 /path/to/folder

    # Download all artifacts from latest pipeline of current branch
    idf-ci gitlab download_artifacts

    # Download debug artifacts from latest pipeline of a specific branch
    idf-ci gitlab download_artifacts --type debug --branch feature/new-feature

**Without S3 Access**
~~~~~~~~~~~~~~~~~~~~~

When you don't have direct S3 credentials but have GitLab access, you can download artifacts using the pipeline ID. The system will first download the presigned JSON using your GitLab account, then use the presigned URLs to download the artifacts.

Supported Options:

- ``--type [...]`` - Type of artifacts to download (if not specified, downloads all types)
- ``--pipeline-id PIPELINE_ID`` - Main pipeline ID to download artifacts from

Examples:

.. code-block:: bash

    # Download all artifacts from a specific pipeline under the current directory
    idf-ci gitlab download_artifacts --pipeline-id 12345

    # Download only debug artifacts from a specific pipeline under a specific folder
    idf-ci gitlab download_artifacts --pipeline-id 12345 --type debug /path/to/folder

    # Download flash artifacts from a specific pipeline
    idf-ci gitlab download_artifacts --pipeline-id 12345 --type flash

Artifact Types Details
++++++++++++++++++++++

The following artifact types are supported:

1. **Flash artifacts** (``--type flash``):

   - Bootloader binaries (``**/build*/bootloader/*.bin``)
   - Application binaries (``**/build*/*.bin``)
   - Partition table binaries (``**/build*/partition_table/*.bin``)
   - Flasher arguments (``**/build*/flasher_args.json``, ``**/build*/flash_project_args``)
   - Configuration files (``**/build*/config/sdkconfig.json``, ``**/build*/sdkconfig``)
   - Project information (``**/build*/project_description.json``)

2. **Debug artifacts** (``--type debug``):

   - Map files (``**/build*/bootloader/*.map``, ``**/build*/*.map``)
   - ELF files (``**/build*/bootloader/*.elf``, ``**/build*/*.elf``)
   - Build logs (``**/build*/build.log``)

Uploading Artifacts
+++++++++++++++++++

To upload artifacts to S3 storage, use the ``upload_artifacts`` command:

.. code-block:: bash

    idf-ci gitlab upload_artifacts [OPTIONS] [FOLDER]

This command uploads artifacts to S3 storage only. GitLab's built-in storage is not supported. The commit SHA is required to identify where to store the artifacts. Only the artifacts under the specified folder will be downloaded in-place. If no folder is specified, the artifacts under the current directory will be downloaded.

Options:

- ``--type [debug|flash]`` - Type of artifacts to upload
- ``--commit-sha COMMIT_SHA`` - Commit SHA to upload artifacts to (required)
- ``--branch BRANCH`` - Git branch to use (if not provided, will use current git branch)

Example:

.. code-block:: bash

    # Upload all debug artifacts from current directory to a specific commit
    idf-ci gitlab upload_artifacts --type debug --commit-sha abc123

    # Upload flash artifacts from a specific directory
    idf-ci gitlab upload_artifacts --type flash --commit-sha abc123 /path/to/build

Generate Presigned URLs
+++++++++++++++++++++++

To generate presigned URLs for artifacts in S3 storage, use the ``generate-presigned-json`` command:

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
++++++++++++++++++++++++++++

To download known failure cases file from S3 storage, use the ``download-known-failure-cases-file`` command:

.. code-block:: bash

    idf-ci gitlab download-known-failure-cases-file FILENAME

This command downloads a known failure cases file from S3 storage. S3 storage must be configured for this command to work.

Implementation Details
++++++++++++++++++++++

Internally, the artifact management commands use the ``ArtifactManager`` class, which handles:

1. GitLab API operations (pipeline, merge request queries)
2. S3 storage operations (artifact upload/download)
3. Fallback to GitLab storage when S3 is not configured

The artifacts are stored with a prefix that includes the project ID and commit SHA: ``{project_namespace}/{project_name}/{commit_sha}/path/to/artifact``

This structure ensures artifacts are properly organized and can be easily located by commit.

CI Pipeline
-----------

Usually in each CI pipeline we have two stages:

- build
- test

``build`` stage is responsible for building the test apps, which compiled the binaries required by running the tests, and target test is

``test`` stage is responsible for running the tests.
