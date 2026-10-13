---
name: idf-ci
description: Use idf-ci to build and test ESP-IDF projects, generate GitLab pipelines, and manage artifacts.
version: 0.1.0
license: Apache-2.0
metadata:
  hermes:
    tags: [esp-idf, ci, build, pytest, gitlab]
---

# Use idf-ci in an ESP-IDF project

Use this skill when the project depends on `idf-ci` for app builds, pytest collection, GitLab child pipelines, or S3 artifacts. It is for **using the CLI in a consuming project**, not for developing the `idf-ci` package.

## Before choosing a command

1. Work from the consuming project's root. Check its `.idf_ci.toml`, `.idf_build_apps.toml`, `pytest.ini`, and CI configuration; don't create or overwrite them merely to inspect a command.
2. Check `idf-ci --help`, then `idf-ci <group> --help`, then `idf-ci <group> <command> --help`. The **installed version's help wins** over the examples below. If `idf-ci` is not installed, find the project's Python environment or ask how it installs CI dependencies; don't silently install a different version.
3. To inspect a config key, use `idf-ci config explain KEY` (type/default/description) and `idf-ci config show KEY` (effective value/source). Use global `--config-file PATH` to choose a file, or repeatable `--config 'path.to.key = value'` for temporary overrides. Values follow Python literal syntax (e.g. `True`, `3`, `"text"`, `['esp32']`); global options go **before** the subcommand.
4. Check environment variables against [the reference](references/environment.md). Their names, separators, and types are not interchangeable with CLI flags or TOML keys. Never expose token/key values when diagnosing CI.

## Command map

| Goal | Command | Important inputs / effect |
| --- | --- | --- |
| Generate starter configuration | `idf-ci init`, `idf-ci build init`, `idf-ci test init` | Writes `.idf_ci.toml`, `.idf_build_apps.toml`, or `pytest.ini`. Check for existing files first. |
| Preview app selection | `idf-ci build run --dry-run -t esp32 -p PATH` | `-p/--paths` is repeatable; `-t/--target` selects a chip; `--modified-files` takes semicolon-separated paths; `--only-test-related` and `--only-non-test-related` are mutually exclusive. |
| Build apps | `idf-ci build run -t esp32 -p PATH` | Same filters as dry run; `--parallel-count` and `--parallel-index` split work. Actually builds apps. |
| Inventory apps | `idf-ci build collect -p PATH --format json` | JSON by default; `-o/--output` writes a file, otherwise stdout. |
| Inventory tests | `idf-ci test collect -t esp32 PATH` | `-k/--filter-expr`, `-m/--marker-expr`, `--format raw|github`, `-o/--output`. Collection does not run hardware tests. |
| Generate GitLab CI | `idf-ci gitlab build-child-pipeline [YAML_OUTPUT]`, `idf-ci gitlab test-child-pipeline [YAML_OUTPUT]` | Check `--help`, project settings, paths and env first. Generates pipeline files and collected app lists; not a dry run. |
| Dynamic CI settings | `idf-ci gitlab pipeline-variables` | Emits `KEY=VALUE` lines derived from pipeline context; inspect output before sourcing it. |
| Fetch/store artifacts | `idf-ci gitlab download-artifacts [FOLDER]`, `idf-ci gitlab upload-artifacts [FOLDER]` | S3 credentials or presigned URL/pipeline ID for downloads; upload requires S3 and changes remote state. Confirm project, commit SHA, branch, destination/type before running. |
| Presigned links | `idf-ci gitlab generate-presigned-json [FOLDER]` | Generates expiring download URLs. Treat the resulting JSON as sensitive access material. |

`idf-ci config get-modified-components` and `idf-ci completions` also exist; inspect their help when needed. For actual pytest execution, use the consuming project's pytest configuration and `pytest --help` (the installed `idf-ci` pytest plugin adds options). A collection-only check is `pytest --collect-only`; hardware tests can require connected devices.

## Worked choices

- **Which apps would build for ESP32?** `idf-ci build run --dry-run -t esp32 -p PATH`. Review the list before dropping `--dry-run`.
- **Which tests match a filter?** `idf-ci test collect -t esp32 -k EXPR PATH`. Use the test command's help to confirm the filter and output format.
- **Why is a GitLab test job excluded?** Inspect `idf-ci config show gitlab.test_pipeline.exclude_runner_tags`, then the `EXCLUDE_RUNNER_TAGS` rules in [the reference](references/environment.md). These rules affect generated jobs, not pytest collection.

## Guardrails

- Run read-only discovery first. Confirm scope before a build, hardware test, generated file overwrite, GitLab API operation, S3 transfer, or uploading artifacts. Do not infer that a command is harmless solely from its name.
- Use existing secret injection (CI masked variables or the project's secret store). Never put credentials in shell arguments, chat, committed files, or diagnostic output. Do not print full environment dumps.
- When help, the consuming project's configuration, and this skill disagree, follow the **installed CLI** and report the discrepancy. Detailed upstream docs: https://docs.espressif.com/projects/idf-ci/en/latest/.
