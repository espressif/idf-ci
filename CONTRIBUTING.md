# Contributing to idf-ci

Thanks for your interest in improving `idf-ci`.

This guide is intentionally short. For detailed usage, see the main `README.md` and the documentation in `docs/`.

## Supported ESP-IDF Versions

The following table shows the supported ESP-IDF versions and the corresponding Python versions.

| ESP-IDF Version | ESP-IDF Version EOL | ESP-IDF Minimum Python Version | idf-build-apps Releases | pytest-embedded Releases |
| --------------- | ------------------- | ------------------------------ | ----------------------- | ------------------------- |
| 5.2             | 2026.08.16          | 3.8                            | 2.x                     | 1.x                     |
| 5.3             | 2027.01.25          | 3.8                            | 2.x                     |1.x                     |
| 5.4             | 2027.07.05          | 3.8                            | 2.x                     |1.x                     |
| 5.5             | 2028.01.21          | 3.9                            | 2.x                     |1.x                     |
| 6.0             | N/A                 | 3.10                           | 3.x                     |2.x                     |
| 6.1 (master)    | N/A                 | 3.10                           | 3.x                     |2.x                     |

To ensure all features work across the supported ESP-IDF versions, we must support the minimum Python version required by each ESP-IDF release. For example, as of 2026-03-19, the minimum Python version we support is 3.8.

## Set Up the Dev Environment

```
uv venv --python 3.8
uv sync --upgrade --all-extras
. ./.venv/bin/activate
```

## Run Tests

```
pytest
```

## Build Docs

```
sphinx-build docs/en docs/en/_build
```

For macOS users, you may open the built docs with:

```
open docs/en/_build/index.html
```

For Linux users, you may open the built docs with:

```
google-chrome docs/en/_build/index.html
```

or

```
firefox docs/en/_build/index.html
```
