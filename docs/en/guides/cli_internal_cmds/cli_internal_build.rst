################
 Build Commands
################

This section documents internal build-related commands.

************************
 build upload-app-sizes
************************

To upload application sizes to the Infra Dashboard, use the ``upload-app-sizes`` command:

.. code-block:: bash

    idf-ci build upload-app-sizes [PATTERN] [OPTIONS]

This command searches for JUnit XML report files matching the specified glob pattern, extracts the build size information and uploads it.

Arguments:

- ``PATTERN`` - Glob pattern for JUnit XML files (default: ``**/build_summary_*.xml``)

Options:

- ``--job-token TOKEN`` - GitLab CI job token for authentication (can also be specified via the ``CI_JOB_TOKEN`` environment variable)
- ``--private-token TOKEN`` - GitLab personal access token for authentication
- ``--commit-sha SHA`` - Commit SHA (can also be specified via the ``CI_COMMIT_SHA`` environment variable)

For GitLab authentication at least one token must be specified. If both are provided, the GitLab CI job token takes precedence over the personal access token.

Required environment variables:

- ``INFRA_DASHBOARD_API_URL`` - Infra Dashboard API URL
- ``INFRA_DASHBOARD_PROJECT_ID`` - Project ID where the sizes will be uploaded

Examples:

.. code-block:: bash

    export INFRA_DASHBOARD_API_URL="https://infra-db.example.com/api"
    export INFRA_DASHBOARD_PROJECT_ID="42"

    # Upload size information using default pattern
    idf-ci build upload-app-sizes --job-token "my-job-token" --commit-sha "a1b2c3d4e5f6..."

    # Specify a custom glob pattern for XML reports
    idf-ci build upload-app-sizes "build_report_*.xml" --job-token "my-job-token" --commit-sha "a1b2c3d4e5f6..."
