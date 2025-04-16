# Changelog

## v0.1.13 (2025-04-16)

### Feat

- support `pre_yaml_jinja` for injecting
- support nightly run pipeline

### Refactor

- revert the rename from PIPELINE_COMMIT_SHA to IDF_CI_REAL_COMMIT_SHA

### Fix

- using default `.post` stage
- detection of CI_PYTHON_CONSTRAINT_BRANCH must be valid string

## v0.1.12 (2025-04-14)

### Feat

- support build job tag defined in settings

## v0.1.11 (2025-04-14)

### Fix

- default test stage
- small fixes on the default values of ci settings

## v0.1.10 (2025-04-10)

### Refactor

- settings sub sections

## v0.1.9 (2025-04-10)

### Feat

- support idf-ci gitlab test-child-pipeline
- support idf-ci test collect --format gitlab
- generate build child pipeline, upload ci artifacts
- generate full build child pipeline
- support gitlab child pipeline
- support `collected_test_related_apps_filepath` and `collected_non_test_related_apps_filepath`
- support `extra_default_build_targets` in .idf_ci.toml
- support generate more gitlab env vars
- support gitlab artifacts download/upload
- support -m -k in both `idf-ci build run` and `idf-ci test collect`
- support local env vars in .idf_ci.toml

### Refactor

- make undefined complete
- small improvements and docstring improvements

## v0.1.8 (2025-03-24)

### Fix

- plugin load sequence. idf-ci must load after pytest-embedded

## v0.1.7 (2025-03-24)

### Fix

- make sure the plugin override sequence

## v0.1.6 (2025-03-21)

### Fix

- remove duplicated sub folders while pytest collection

## v0.1.5 (2025-03-13)

### Fix

- `env_selector` shall return markers with `and` joined

## v0.1.4 (2025-03-13)

### Feat

- support `idf-ci test collect`
- support `env_markers` in ini file

### Fix

- solve name collision in `idf_ci.cli`
- avoid `cli` name conflict as sub-package and cli function
- package data includes dotfiles
- stop overriding existing config files

## v0.1.3 (2025-02-20)

### Feat

- replace concept "profile" to concept "config file"
- drop profile overriding. use only one profile

### Fix

- load only apps which are built successfully
- calculate os.getcwd() dynamically
- setup same logging level for different packages
- get current workdir when called init-profile

### Refactor

- change all `LOGGER` to `logger`

## v0.1.2 (2025-02-10)

### Fix

- return all apps as non-test-related apps when no pytest case found

## v0.1.1 (2025-02-10)

### Fix

- pass modified_files and modified_components to build_apps call

## v0.1.0 (2025-02-07)
