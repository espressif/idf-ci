# Changelog

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
