################################
 idf-ci |version| Documentation
################################

This documentation describes idf-ci, a tool designed to streamline CI/CD for ESP-IDF projects, with support for both GitLab CI/CD and GitHub Actions.

**Key Features:**

- **Sensible Defaults**

  Easy setup with default settings for idf-build-apps_ and pytest-embedded_.

- **Build Management**

  Build ESP-IDF apps for multiple targets (ESP32, ESP32-S2, ESP32-C3, etc.) with parallel builds and filtering based on changed files or test needs.

- **Test Management**

  Run pytest with ESP-IDF configs, including target-specific test discovery and marker filtering.

- **GitLab CI/CD Integration**

  Full pipeline support with artifacts, S3 uploads, and auto-generated jobs for builds and tests.

- **GitHub Actions Integration**

  Generate a test matrix from project settings.

- **Configuration Visibility**

  Inspect resolved configuration values, defaults, and override sources.

.. toctree::
    :maxdepth: 1
    :caption: Explanations
    :glob:

    explanations/*

.. toctree::
    :maxdepth: 2
    :caption: Guides
    :glob:

    guides/*

.. toctree::
    :maxdepth: 1
    :caption: References
    :glob:

    references/*
    references/api/modules.rst

.. _idf-build-apps: https://github.com/espressif/idf-build-apps

.. _pytest: https://docs.pytest.org/en/stable/

.. _pytest-embedded: https://github.com/espressif/pytest-embedded
