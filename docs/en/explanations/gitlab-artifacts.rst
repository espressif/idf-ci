##################
 GitLab Artifacts
##################

``idf-ci`` has two artifact mechanisms under ``gitlab.artifacts``:

- ``gitlab.artifacts.native`` configures files collected by generated GitLab CI jobs.
- ``gitlab.artifacts.s3`` configures artifact types managed explicitly by ``idf-ci`` commands and stored in S3-compatible object storage.

They solve different problems.

GitLab native artifacts are attached to GitLab jobs and are described only by file patterns. S3 artifacts are typed, can be uploaded and downloaded independently of a GitLab job, and support presigned URL distribution when direct S3 credentials are not available.

****************************
 Native and S3 are separate
****************************

The two backends are configured under the same top-level section, but they are not interchangeable.

``gitlab.artifacts.native``
    Controls the ``artifacts:`` sections emitted in generated GitLab pipeline YAML. The default build patterns collect build outputs such as ``*.bin``, ``*.elf``, ``*.map``, ``build.log``, ``app_info_*.txt``, and ``build_summary_*.xml``. The default test patterns collect ``pytest-embedded/`` and ``XUNIT_RESULT*.xml``.

``gitlab.artifacts.s3``
    Controls the behavior of ``idf-ci gitlab upload-artifacts``, ``download-artifacts``, and ``generate-presigned-json``. S3 artifacts are grouped by artifact type, and each type has its own matching rules and destination bucket.

Enabling or disabling one backend does not automatically affect the other. In particular, ``upload-artifacts`` and ``download-artifacts`` only operate on ``gitlab.artifacts.s3``.

************************
 S3 artifacts are typed
************************

The S3 backend is organized as a mapping from artifact type name to configuration:

.. code-block:: toml

    [gitlab.artifacts.s3]
    enable = true

    [gitlab.artifacts.s3.configs.debug]
    bucket = "idf-artifacts"
    build_dir_pattern = "**/build*/"
    patterns = ["*.elf", "*.map", "build.log"]

Each entry under ``gitlab.artifacts.s3.configs`` is an ``S3ArtifactConfig`` with these behavioral fields:

``bucket``
    Bucket that stores objects for this artifact type.

``is_public``
    If ``true``, downloads use the public S3 client. Uploads still require the authenticated client.

``zip_first``
    If ``true``, files are first packed into ``<artifact_type>.zip`` per matched build directory, then that zip file is uploaded. If ``false``, matching files are uploaded individually.

``build_dir_pattern``
    Glob used to discover build directories. Patterns in ``patterns`` are evaluated relative to each matched directory. If omitted, the command's effective folder is the only build directory.

``patterns``
    Glob patterns selecting files to upload or download. For zipped types, they define zip contents. For non-zipped types, they define the files transferred directly.

``if_clause``
    Optional boolean expression that decides whether the type is active. If it evaluates to false, the type is skipped. If evaluation fails, the type is also skipped and only a debug log is emitted.

By default, ``idf-ci`` defines ``debug`` and ``flash`` S3 types. Both use ``build_dir_pattern = "**/build*/"``. ``debug`` collects ``.map``, ``.elf``, and ``build.log``. ``flash`` collects binaries and flashing metadata such as ``flasher_args.json`` and ``project_description.json``.

***************************************
 Artifact type selection happens first
***************************************

Every S3 command resolves the final list of artifact types before touching storage.

- If ``--type`` is provided, only that configured type is considered.
- If ``--type`` is omitted, all configured types are considered.
- ``if_clause`` filtering is then applied.
- If a requested type exists but its ``if_clause`` disables it, the command does not fail; it simply processes zero items for that type.

This means type selection is configuration-driven rather than inferred from what files happen to exist on disk.

************************
 Upload path resolution
************************

The S3 commands work from an effective root called ``from_path``:

- If ``FOLDER`` is passed on the command line, ``from_path`` is that path.
- Otherwise, ``from_path`` is the current working directory.

The commit SHA is resolved independently, in this order:

1. explicit ``--commit-sha``
2. ``PIPELINE_COMMIT_SHA``
3. ``git rev-parse <branch>``, where ``<branch>`` is ``--branch`` or the current Git branch

For uploads, build directories are resolved as follows:

- If ``--build-dir`` is provided, it overrides ``build_dir_pattern`` and exactly one directory is used.
- A relative ``--build-dir`` is interpreted relative to ``from_path``.
- An absolute ``--build-dir`` is used as-is.
- If ``--build-dir`` is not provided and ``build_dir_pattern`` is set, all matching directories under ``from_path`` are used.
- If neither is set, ``from_path`` itself is the build directory.

For each resolved build directory:

- when ``zip_first = true``, matching files are added to ``<artifact_type>.zip`` with paths relative to that build directory
- when ``zip_first = false``, each matching file is uploaded directly

If a zipped type finds no matching files in a build directory, no zip file is created for that directory.

******************
 S3 object layout
******************

All S3 object keys begin with this prefix:

.. code-block:: text

    <gitlab.project>/<commit_sha>/

The remainder of the object key is derived from the artifact path relative to the effective project root:

- if ``from_path`` is relative, paths are stored relative to that relative path
- if ``from_path`` is absolute, paths are rewritten relative to ``IDF_PATH``

In practice, uploads preserve the directory structure below the project root.

For example, with:

- ``gitlab.project = "espressif/esp-idf"``
- ``commit_sha = abc123``
- a matched build directory ``app/build_esp32_build``

the stored object names are:

.. code-block:: text

    espressif/esp-idf/abc123/app/build_esp32_build/debug.zip
    espressif/esp-idf/abc123/app/build_esp32_build/flash.zip
    espressif/esp-idf/abc123/app/build_esp32_build/size.json

This layout is important because downloads, presigned URL generation, and pipeline-based retrieval all assume the same prefix and relative path scheme.

*******************
 Download behavior
*******************

``download-artifacts`` supports two transport modes.

Direct S3 download
==================

When no presigned JSON input is provided, the command lists objects directly from S3 under:

.. code-block:: text

    <gitlab.project>/<commit_sha>/<from_path>

If ``--build-dir`` is provided, downloads are limited to that build directory only. A relative ``--build-dir`` is interpreted relative to ``from_path``. An absolute ``--build-dir`` is used as-is.

For non-zipped artifact types, objects are filtered against the configured file patterns and written back under ``IDF_PATH`` using the same relative path.

For zipped artifact types, the command looks for files named exactly ``<artifact_type>.zip``. Each downloaded zip is extracted into its parent directory and then deleted. The extracted files therefore appear as ordinary files in the local tree rather than as retained archives.

Presigned JSON download
=======================

When ``--presigned-json`` is supplied, the command does not talk to S3 directly. Instead, it reads a JSON object that maps relative artifact paths to presigned URLs:

.. code-block:: json

    {
      "app/build_esp32_build/flash.zip": "https://...",
      "app/build_esp32_build/size.json": "https://..."
    }

``--build-dir`` applies here as well: it narrows the selected JSON entries to one build directory before files are downloaded or zip files are extracted.

For non-zipped types, entries are filtered using the same effective patterns used for direct S3 download.

For zipped types, the command selects keys whose filename is ``<artifact_type>.zip`` and whose parent path is under the requested folder, if one was provided. Each archive is downloaded, extracted in place, and then removed.

******************************************
 How ``--pipeline-id`` fits into the flow
******************************************

``download-artifacts --pipeline-id`` is a two-step indirection:

1. use the GitLab API to find the configured build child pipeline
2. download ``presigned.json`` from the configured job artifact

The lookup uses two configuration keys from ``gitlab.build_pipeline``:

- ``workflow_name`` identifies the downstream build child pipeline
- ``presigned_json_job_name`` identifies the job that published ``presigned.json``

The downloaded file is cached locally under the system temporary directory:

.. code-block:: text

    .cache/idf-ci/presigned_json/<pipeline_id>/presigned.json

After that, the normal presigned JSON download path is used.

*****************************
 Public and authenticated S3
*****************************

Uploads always require an authenticated S3 client.

Downloads behave differently:

- if ``is_public = false``, downloads require the authenticated S3 client
- if ``is_public = true``, downloads use the public client instead

This allows a configuration where some artifact types are distributed publicly while others remain private.

**************************
 Generated presigned JSON
**************************

``generate-presigned-json`` enumerates the same S3 objects that a download would target and emits a mapping from relative artifact path to presigned GET URL.

The output shape depends on ``zip_first``:

- zipped types contribute ``<artifact_type>.zip`` entries
- non-zipped types contribute individual file entries

The generated JSON is therefore a transport description, not a manifest of extracted local files.

*******************************
 Native artifact key migration
*******************************

Two legacy keys are still recognized:

- ``gitlab.artifacts.build_job_filepatterns``
- ``gitlab.artifacts.test_job_filepatterns``

At load time, ``idf-ci`` migrates them to:

- ``gitlab.artifacts.native.build_job_filepatterns``
- ``gitlab.artifacts.native.test_job_filepatterns``

If both the legacy key and the new ``native`` key are present, the ``native`` key wins and a deprecation warning is emitted.

**********************
 Practical boundaries
**********************

The artifact subsystem has a few deliberate boundaries:

- GitLab native artifacts describe what CI jobs keep in GitLab storage.
- S3 artifact commands do not upload into GitLab's native artifact storage.
- Presigned downloads require either an existing ``presigned.json`` file or a GitLab pipeline whose child pipeline and publishing job can be discovered from configuration. The file could be generated by ``idf-ci gitlab generate-presigned-json``.
- Artifact selection is driven by configured types and patterns, not by a schema embedded in the uploaded objects.

For command syntax, see :doc:`../guides/cli_group_cmds/cli_gitlab`. For full field definitions and defaults, see :doc:`../references/ci-config-file`.
