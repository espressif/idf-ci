# idf-ci

[![Documentation Status](https://readthedocs.com/projects/espressif-idf-ci/badge/?version=latest)](https://espressif-idf-ci.readthedocs-hosted.com/en/latest/)
![Python 3.7+](https://img.shields.io/pypi/pyversions/idf-ci)

Python toolkit for CI/CD of ESP-IDF projects.

> [!WARNING]
> This project is still under development. All APIs are subject to change.

## Installation

```bash
pip install -U idf-ci
```

## Basic Usage

### Initialize Configuration Files

```bash
# Create .idf_ci.toml with default idf-ci settings
idf-ci init

# Create .idf_build_apps.toml with default build settings
idf-ci build init

# Create pytest.ini with default test settings
idf-ci test init
```

### Build Apps

```bash
# Build all apps
idf-ci build run

# Build apps for specific target
idf-ci build run -t esp32

# Build only test-related apps
idf-ci build run --only-test-related

# Preview what would be built (dry run)
idf-ci build run --dry-run
```

### Run Tests

We implement a pytest plugin to run tests with sensible defaults with another plugin [pytest-embedded](https://github.com/espressif/pytest-embedded)

```bash
# Only collect tests that would run
pytest --collect-only

# Run tests with target esp32
pytest --target esp32
```

## Documentation

For detailed usage and configuration options, please refer to the [documentation](https://espressif-idf-ci.readthedocs-hosted.com/en/latest/).
