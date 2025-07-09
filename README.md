# idf-ci

[![Documentation Status](https://readthedocs.com/projects/espressif-idf-ci/badge/?version=latest)](https://espressif-idf-ci.readthedocs-hosted.com/en/latest/)
![Python 3.7+](https://img.shields.io/pypi/pyversions/idf-ci)

A tool designed to streamline the CI/CD of ESP-IDF projects, with support for both GitLab CI/CD and GitHub Actions.

## Installation

```bash
pip install -U idf-ci
```

## Key Features

- **Sensible Defaults**

  Easy setup with default settings for [idf-build-apps](https://github.com/espressif/idf-build-apps) and [pytest-embedded](https://github.com/espressif/pytest-embedded)

- **Build Management**

  Build ESP-IDF apps for multiple targets (ESP32, ESP32-S2, ESP32-C3, etc.) with parallel builds and smart filtering based on changed files or test needs.

- **Test Management**

  Run `pytest` with ESP-IDF configs, including target-specific test discovery and marker filtering.

- **GitLab CI/CD Integration**

  Full pipeline support with artifacts, S3 uploads, and auto-generated jobs for builds and tests.

- **GitHub Actions Integration**

  Generate test matrix from project settings.

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
