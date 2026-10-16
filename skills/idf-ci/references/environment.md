# idf-ci environment variables

These are **environment variables**, not CLI flags. Names, types, and defaults come from `GitlabEnvVars` in `idf_ci/envs.py` in the upstream `idf-ci` source. Check the version installed in the consuming project before relying on a variable; a missing value does not mean a feature is enabled. Prefer project/CI secret management for sensitive variables.

## Build and test selection

| Variable | Type / input | Purpose |
| --- | --- | --- |
| `IDF_PATH` | path; default `''` | ESP-IDF directory; also consulted by settings. |
| `IDF_TOOLCHAIN` | string | Toolchain for build manifests and collected app lists. |
| `CHANGED_FILES_SEMICOLON_SEPARATED` | semicolon-separated paths | Changed files from the pipeline. |
| `IDF_CI_SELECT_BY_TARGETS` | comma-separated chip targets, e.g. `esp32,esp32c3` | Restrict build/test targets. |
| `IDF_CI_SELECT_BY_FILTER_EXPR` | pytest `-k`-style expression | Select cases using a filter expression. Ignored with a warning when `IDF_CI_SELECT_ALL_PYTEST_CASES=1`. |
| `IDF_CI_SELECT_ALL_PYTEST_CASES` | boolean | Select all pytest cases, ignoring modified-file dependency selection and `IDF_CI_SELECT_BY_FILTER_EXPR`. Does not bypass manifest test-target filtering when that filter is enabled. |
| `IDF_CI_FILTER_PYTEST_CASES_BY_MANIFEST_TEST_TARGETS` | boolean; default `false` | Opt in to excluding generated pytest cases if any DUT app is disabled by manifest `enable`, `disable`, or `disable_test` rules for the selected toolchain. Does not evaluate `depends_*` or filter explicitly supplied cases. |
| `IDF_CI_BUILD_ONLY_TEST_RELATED_APPS` | boolean | Build only test-related apps. |
| `IDF_CI_BUILD_ONLY_NON_TEST_RELATED_APPS` | boolean | Build only non-test-related apps. **Do not enable both** build-only variables; idf-ci rejects that combination. |
| `IDF_CI_ARTIFACT_NAMESPACE` | letters, digits, `_` or `-` only | Separate S3 artifacts for build variants of the same commit. |

## GitLab pipeline context

| Variable | Type / input | Purpose |
| --- | --- | --- |
| `CI_COMMIT_SHA` | commit SHA | GitLab predefined commit SHA. |
| `CI_MERGE_REQUEST_IID` | ID | GitLab merge request number. |
| `CI_MERGE_REQUEST_SOURCE_BRANCH_SHA` | commit SHA | Merge request source SHA. |
| `CI_MERGE_REQUEST_LABELS` | comma-separated labels | Labels considered during pipeline selection. |
| `CI_MERGE_REQUEST_DESCRIPTION` | text | MR description. |
| `CI_PYTHON_CONSTRAINT_BRANCH` | branch string | Python constraint branch used by CI. |
| `PIPELINE_COMMIT_SHA` | commit SHA | Source-branch SHA rather than merge-result SHA; artifact commands try it before the branch tip when no `--commit-sha` is given. |
| `INCLUDE_NIGHTLY_RUN` | string | Include nightly jobs/cases. |
| `NIGHTLY_RUN` | string | Run only nightly jobs/cases. |
| `IDF_CI_IS_DEBUG_PIPELINE` | boolean | Mark a debug pipeline. |
| `EXCLUDE_RUNNER_TAGS` | semicolon-separated rules | Exclude generated test jobs by runner tags. `esp32,ip101` matches an exact tag set; `esp32,ip101,*` matches sets containing both tags. Does not change pytest collection. |

## GitLab API and S3

| Variable | Type / input | Purpose |
| --- | --- | --- |
| `GITLAB_HTTPS_SERVER` | URL; default `https://gitlab.com` | GitLab API server. |
| `GITLAB_ACCESS_TOKEN` | **secret** | GitLab API authentication. |
| `IDF_S3_SERVER` | URL | S3 endpoint. |
| `IDF_S3_ACCESS_KEY` | **secret** | S3 access key. |
| `IDF_S3_SECRET_KEY` | **secret** | S3 secret key. |
| `IDF_S3_TIMEOUT_TOTAL` | float; default `300.0` seconds | S3 request timeout. |

`idf-ci` reads the supported values from the current environment when needed; different commands use different subsets. A variable's presence here does **not** mean every command requires it. Check `idf-ci <group> <command> --help` and the consuming project's `.idf_ci.toml` before setting anything. Never echo secret values or embed them in an example.

Upstream source: https://github.com/espressif/idf-ci/blob/main/idf_ci/envs.py
