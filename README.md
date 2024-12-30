# idf-ci

This repo contains the tools for CI/CD of ESP-IDF projects.

## `idf-ci` Python Package

## Configurations

`.idf_ci.toml` is the configuration file for `idf-ci-build-test`. It is a TOML file. The following reflects the default configurations:

```toml
# how to map the modified files into modified components
component_mapping_regexes = [
    "/components/(.+)/",
    "/common_components/(.+)/",
]
extend_component_mapping_regexes = []

# these files would be ignored when mapping the modified files into modified components
component_ignored_file_extensions = [
    ".md",
    ".rst",
    ".yaml",
    ".yml",
    ".py",
]
extend_component_ignored_file_extensions = []
```

## Gitlab CI/CD Catalog

CI/CD catalogs are defined inside `templates/` directory.

### `mr-modified-files`

To use this template, add the following to your `.gitlab-ci.yml`:

```yml
include:
  - component: $CI_SERVER_FQDN/espressif/idf-ci/mr-modified-files@main
```

For detailed inputs, please refer to the [template file](templates/mr-modified-files.yml).
