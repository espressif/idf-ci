# idf-ci

This repo contains the tools for CI/CD of ESP-IDF projects.

## Configurations

`.idf_ci.toml` is the configuration file for `idf-ci-build-test`. It is a TOML file. The following reflects the default configurations:

```toml
# how to map the modified files into modified components
component_mapping_regexes = [
    "/components/(.+)/",
    "/common_components/(.+)/",
]
extend_component_mapping_regexes = []
```
