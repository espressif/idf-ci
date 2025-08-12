<a href="https://www.espressif.com">
    <img src="https://www.espressif.com/sites/all/themes/espressif/logo-black.svg" align="right" height="20" />
</a>

# CHANGELOG

> All notable changes to this project are documented in this file.
> This list is not exhaustive - only important changes, fixes, and new features in the code are reflected here.

<div style="text-align: center;">
    <a href="https://keepachangelog.com/en/1.1.0/">
        <img alt="Static Badge" src="https://img.shields.io/badge/Keep%20a%20Changelog-v1.1.0-salmon?logo=keepachangelog&logoColor=black&labelColor=white&link=https%3A%2F%2Fkeepachangelog.com%2Fen%2F1.1.0%2F">
    </a>
    <a href="https://www.conventionalcommits.org/en/v1.0.0/">
        <img alt="Static Badge" src="https://img.shields.io/badge/Conventional%20Commits-v1.0.0-pink?logo=conventionalcommits&logoColor=black&labelColor=white&link=https%3A%2F%2Fwww.conventionalcommits.org%2Fen%2Fv1.0.0%2F">
    </a>
    <a href="https://semver.org/spec/v2.0.0.html">
        <img alt="Static Badge" src="https://img.shields.io/badge/Semantic%20Versioning-v2.0.0-grey?logo=semanticrelease&logoColor=black&labelColor=white&link=https%3A%2F%2Fsemver.org%2Fspec%2Fv2.0.0.html">
    </a>
</div>
<hr>

## v0.3.0 (2025-08-12)

### ✨ New Features

- show upload and download time *(Fu Hanxi - 2a3263b)*
- support `exclude_dirs` in `.idf_ci.toml` *(Fu Hanxi - 00abb2f)*

### 🐛 Bug Fixes

- use `DEFAULT_BUILD_TARGETS.get()` instead of `SUPPORTED_TARGETS` *(Fu Hanxi - 3f7926a)*

### 🏗️ Changes

- depends on idf-build-apps~=2.12 *(Fu Hanxi - 6a3cb6a)*


## v0.2.7 (2025-08-05)

### 🐛 Bug Fixes

- remove non-existent folders from list *(igor.udot - 51b446e)*


## v0.2.6 (2025-07-21)

### 🐛 Bug Fixes

- filter test script by .py extension. not by filename *(Fu Hanxi - 25b2f20)*


## v0.2.5 (2025-07-14)

### ✨ New Features

- support CiSettings.component_mapping_exclude_regexes *(Fu Hanxi - 13de062)*

### 🐛 Bug Fixes

- lazy matching component regex while `get_modified_components` *(Fu Hanxi - 44151f9)*


## v0.2.4 (2025-07-11)

### 🐛 Bug Fixes

- **build**: will only build test-related apps when `-k` or `-m` is passed *(Fu Hanxi - c32360d)*


## v0.2.3 (2025-07-09)

### 🐛 Bug Fixes

- **fake_pass**: add `workflow:rules:always` to avoid empty pipeline *(Fu Hanxi - a6c828b)*


## v0.2.2 (2025-07-09)

### 🐛 Bug Fixes

- **fake_pass**: simplify the job, inherit build pipeline job stage and tags *(Fu Hanxi - abf4c3f)*


## v0.2.1 (2025-07-09)

### ✨ New Features

- support declare `job_stage` in pipeline settings *(Fu Hanxi - f902e01)*

### 🐛 Bug Fixes

- reuse job template for `fake_pass` jobs *(Fu Hanxi - 20b3648)*

### 📖 Documentation

- **gitlab artifact**: download without s3 access *(Fu Hanxi - ea39918)*
- update readme. add key features *(Fu Hanxi - 9442434)*
- reorganize cli guide. add global cli commands and options *(Fu Hanxi - 33de0a6)*
- more related links *(Fu Hanxi - 428a70a)*


## v0.2.0 (2025-07-08)

### 🐛 Bug Fixes

- job name env selector use comma, instead of "and" *(Fu Hanxi - 1579603)*

## v0.1.35 (2025-06-30)

### ✨ New Features

- **gitlab**: split test, non-test build jobs *(Fu Hanxi - edd9a65)*

### 🐛 Bug Fixes

- only load apps from local collect files on CI *(Fu Hanxi - bf1f060)*
- remove `is_in_ci` in `PytestCase` class, use `CiSettings().is_in_ci` instead *(Fu Hanxi - 8c2ce79)*

## v0.1.34 (2025-06-18)

### 🐛 Bug Fixes

- gitlab pipeline doublequote the variable *(Fu Hanxi - 6c1094e)*

## v0.1.33 (2025-06-18)

### 🐛 Bug Fixes

- singlequote the nodes in gitlab to avoid special chars issues *(Fu Hanxi - 7be286f)*
- runner tags shall not be concat with '+' *(Fu Hanxi - c242144)*

## v0.1.32 (2025-06-17)

### 🐛 Bug Fixes

- doublequote pipeline variable when contains space or newline *(Fu Hanxi - e178854)*

## v0.1.31 (2025-06-16)

### 🐛 Bug Fixes

- select all pytest cases boolean compare *(Fu Hanxi - 4db9dfe)*

## v0.1.30 (2025-06-11)

### ✨ New Features

- support download artifacts from pipeline id *(Fu Hanxi - 6a401fd)*

## v0.1.29 (2025-06-10)

### 🐛 Bug Fixes

- default build system set to UNDEF *(Fu Hanxi - a4000ae)*

## v0.1.28 (2025-06-03)

### ✨ New Features

- support pass `build_system` as args *(Fu Hanxi - ecfb012)*

### 🐛 Bug Fixes

- download from presigned json *(Fu Hanxi - 05b88e0)*
- paths should be directories *(Fu Hanxi - 89f9af7)*

### 🏗️ Changes

- update idf-build-apps minimum version *(Fu Hanxi - 5904d57)*

## v0.1.26 (2025-05-19)

### ⚡ Performance Improvements

- s3 operations with ThreadPoolExecutor *(Fu Hanxi - 4e6242c)*

## v0.1.25 (2025-05-14)

### 🐛 Bug Fixes

- env file values shall not include doublequotes *(Fu Hanxi - b75b23b)*

## v0.1.24 (2025-05-13)

### ✨ New Features

- support `if_clause` in s3 artifacts *(Fu Hanxi - 826a637)*

## v0.1.23 (2025-05-07)

### ✨ New Features

- support `idf-ci gitlab generate-presigned-json -o/--output` *(Fu Hanxi - dfdec03)*

### 🐛 Bug Fixes

- s3 artifacts support relative path *(Fu Hanxi - 61a0a20)*

## v0.1.22 (2025-05-06)

### ✨ New Features

- support detect commit-sha from local git or env var *(Fu Hanxi - 48ab1fe)*

### 📖 Documentation

- update the docs of the cli usage *(Fu Hanxi - 3ed3887)*

### 🏗️ Changes

- rename `ArtifactsSettings` to `ArtifactSettings` *(Fu Hanxi - 3171c71)*
- remove `metrics` from the default `gitlab.s3` settings *(Fu Hanxi - 1ae3128)*

## v0.1.21 (2025-05-05)

### ⚡ Performance Improvements

- load apps from collect app info files faster *(Fu Hanxi - a790ac5)*
- load settings when needed *(Fu Hanxi - f9a740f)*

## v0.1.20 (2025-04-30)

### 🐛 Bug Fixes

- return apps that belongs to the current concurrent build *(Fu Hanxi - eef11cc)*

## v0.1.19 (2025-04-29)

### 🐛 Bug Fixes

- generate fake_pass job when no apps will be built or no tests will be run *(Fu Hanxi - 7a2e420)*

### 🔧 Code Refactoring

- record additional info in jobs *(Fu Hanxi - 0adb4e9)*

## v0.1.18 (2025-04-29)

### ✨ New Features

- support debug info *(Fu Hanxi - 85bd1d5)*

### 🔧 Code Refactoring

- improve collection, `IdfPytestPlugin.cases` keep original order *(Fu Hanxi - f52f208)*

## v0.1.17 (2025-04-25)

### 🐛 Bug Fixes

- import TypedDict from typing_extensions under python 3.12 *(Fu Hanxi - 53ce70a)*

### 🔧 Code Refactoring

- rename `idf-ci gitlab dynamic-pipeline-variables` to `idf-ci gitlab pipeline-variables` *(Fu Hanxi - 137f93d)*

## v0.1.16 (2025-04-23)

### ✨ New Features

- support `idf-ci gitlab download-artifacts` from presigned json *(Fu Hanxi - ec8ae20)*

## v0.1.15 (2025-04-23)

### ✨ New Features

- support `idf-ci gitlab generate-presigned-json` *(Fu Hanxi - 7bf35e0)*

### 🏗️ Changes

- `gitlab.artifact` settings renamed to `gitlab.artifacts` *(Fu Hanxi - 1d1faa3)*
- `filepatterns` fields under gitlab.artifact renamed to `gitlab.artifact.s3` *(Fu Hanxi - 0d19a58)*
- rename `gitlab.template` related settings names *(Fu Hanxi - cbddd6f)*

## v0.1.14 (2025-04-17)

### 🐛 Bug Fixes

- add marker `nightly_run` at init phase *(Fu Hanxi - 927967e)*

### 🏗️ Changes

- caseid add `_qemu` as an extra identifier *(Fu Hanxi - 1b43569)*

## v0.1.13 (2025-04-16)

### ✨ New Features

- support `pre_yaml_jinja` for injecting *(Fu Hanxi - d5bbb08)*
- support nightly run pipeline *(Fu Hanxi - 041ce9f)*

### 🐛 Bug Fixes

- using default `.post` stage *(Fu Hanxi - 8885914)*
- detection of CI_PYTHON_CONSTRAINT_BRANCH must be valid string *(Fu Hanxi - 232915b)*

### 🔧 Code Refactoring

- revert the rename from PIPELINE_COMMIT_SHA to IDF_CI_REAL_COMMIT_SHA *(Fu Hanxi - 12706b8)*

### 🏗️ Changes

- require idf-build-apps 2.9 *(Fu Hanxi - 9cdbbfd)*

## v0.1.12 (2025-04-14)

### ✨ New Features

- support build job tag defined in settings *(Fu Hanxi - 921aba6)*

## v0.1.11 (2025-04-14)

### 🐛 Bug Fixes

- default test stage *(Fu Hanxi - bf511d3)*
- small fixes on the default values of ci settings *(Fu Hanxi - 4c53332)*

## v0.1.10 (2025-04-10)

### 🔧 Code Refactoring

- settings sub sections *(Fu Hanxi - 83239ba)*

## v0.1.9 (2025-04-10)

### ✨ New Features

- support idf-ci gitlab test-child-pipeline *(Fu Hanxi - efb628d)*
- support idf-ci test collect --format gitlab *(Fu Hanxi - 0a113eb)*
- generate build child pipeline, upload ci artifacts *(Fu Hanxi - 663a6fb)*
- generate full build child pipeline *(Fu Hanxi - e4c0f68)*
- support gitlab child pipeline *(Fu Hanxi - 198050d)*
- support `collected_test_related_apps_filepath` and `collected_non_test_related_apps_filepath` *(Fu Hanxi - 2fbe991)*
- support `extra_default_build_targets` in .idf_ci.toml *(Fu Hanxi - ac31a4e)*
- support generate more gitlab env vars *(Fu Hanxi - fe86ee0)*
- support gitlab artifacts download/upload *(Fu Hanxi - 704da0b)*
- support -m -k in both `idf-ci build run` and `idf-ci test collect` *(Fu Hanxi - b1a619b)*
- support local env vars in .idf_ci.toml *(Fu Hanxi - 46d8374)*

### 📖 Documentation

- update settings and env vars related descriptions *(Fu Hanxi - 794c16a)*
- update gitlab-env-vars *(Fu Hanxi - 5b53094)*
- update ci-config-file *(Fu Hanxi - 9d9a296)*
- update gitlab artifacts *(Fu Hanxi - ffdfc8e)*
- small fixes *(Fu Hanxi - 6854543)*
- fix `templates_path` to make email_off work *(Fu Hanxi - 91b3945)*

### 🔧 Code Refactoring

- make undefined complete *(Fu Hanxi - fd1dc6e)*
- small improvements and docstring improvements *(Fu Hanxi - a696551)*

### 🏗️ Changes

- default logging level set to INFO *(Fu Hanxi - 9ab568b)*
- respect env vars and .idf_ci.toml files in `get_all_apps` *(Fu Hanxi - 82d3df5)*
- docstrfmt format. no trailing line in docstrings *(Fu Hanxi - 99a5a94)*
- use docstrfmt instead of rstfmt *(Fu Hanxi - f211052)*
- unify the cli api of download-artifacts and upload-artifacts *(Fu Hanxi - 15fb0cd)*

## v0.1.8 (2025-03-24)

### 🐛 Bug Fixes

- plugin load sequence. idf-ci must load after pytest-embedded *(Fu Hanxi - 1761709)*

## v0.1.7 (2025-03-24)

### 🐛 Bug Fixes

- make sure the plugin override sequence *(Fu Hanxi - c6827a9)*

## v0.1.6 (2025-03-21)

### 🐛 Bug Fixes

- remove duplicated sub folders while pytest collection *(Fu Hanxi - d05573e)*

### 📖 Documentation

- update recommended gitignore list *(Fu Hanxi - 2b5222b)*

## v0.1.5 (2025-03-13)

### 🐛 Bug Fixes

- `env_selector` shall return markers with `and` joined *(Fu Hanxi - d1271b4)*

## v0.1.4 (2025-03-13)

### ✨ New Features

- support `idf-ci test collect` *(Fu Hanxi - 5e7b0a3)*
- support `env_markers` in ini file *(Fu Hanxi - 4abdfa0)*

### 🐛 Bug Fixes

- solve name collision in `idf_ci.cli` *(Fu Hanxi - 6b98e76)*
- avoid `cli` name conflict as sub-package and cli function *(Fu Hanxi - a9ad2bd)*
- package data includes dotfiles *(Fu Hanxi - eb075ef)*
- stop overriding existing config files *(Fu Hanxi - ad2b946)*

### 🏗️ Changes

- don't use relative import in __all__ *(Fu Hanxi - 5833c17)*
- by default check manifest rules *(Fu Hanxi - 224008f)*

## v0.1.3 (2025-02-20)

### 🚨 Breaking changes

- replace concept "profile" to concept "config file" *(Fu Hanxi - 98c43ab)*
- drop profile overriding. use only one profile *(Fu Hanxi - 14c3422)*

### 🐛 Bug Fixes

- load only apps which are built successfully *(Fu Hanxi - 3f85d37)*
- calculate os.getcwd() dynamically *(Fu Hanxi - 5c8cebc)*
- setup same logging level for different packages *(Fu Hanxi - fb14412)*
- get current workdir when called init-profile *(Fu Hanxi - d44e8a6)*

### 📖 Documentation

- add disclaimer *(Fu Hanxi - 1a7fbda)*
- add gitignore recommendation *(Fu Hanxi - 1c387ea)*
- small writing improvements *(Fu Hanxi - 40d76f6)*
- write merge profiles *(Fu Hanxi - 0b238a7)*
- update README *(Fu Hanxi - 091ed9e)*
- update guides/local_preview *(Fu Hanxi - cf45405)*
- add documentation link in README *(Fu Hanxi - ab30b21)*
- add read-the-docs config file *(Fu Hanxi - 63a6b86)*

### 🔧 Code Refactoring

- change all `LOGGER` to `logger` *(Fu Hanxi - 41b8853)*

### 🏗️ Changes

- test config file default value *(Fu Hanxi - bc3c394)*
- logging via package logger instead of the root logger for a few places *(Fu Hanxi - 1ea74d8)*
- use rich handler defined as idf-build-apps *(Fu Hanxi - c247032)*
- log date format *(Fu Hanxi - 6339856)*
- remove redundant log *(Fu Hanxi - 19c5359)*

## v0.1.2 (2025-02-10)

### 🐛 Bug Fixes

- return all apps as non-test-related apps when no pytest case found *(Fu Hanxi - c5a7888)*

## v0.1.1 (2025-02-10)

### 🐛 Bug Fixes

- pass modified_files and modified_components to build_apps call *(Fu Hanxi - 0d390e4)*

## v0.1.0 (2025-02-07)

### ✨ New Features

- support configure preserve artifacts or not *(Fu Hanxi - a59cc06)*
- support python 3.7 *(Fu Hanxi - bf79b71)*
- support setup logging *(Fu Hanxi - 6b462a6)*
- require `target` defined in param *(Fu Hanxi - 6865174)*
- support run with preset settings in pytest plugin mode *(Fu Hanxi - cd59a0f)*
- support idf-ci as a pytest plugin *(Fu Hanxi - b2bcb38)*
- support filter by app list *(Fu Hanxi - 90c40dd)*
- support filter by marker expr, by default "not host_test" *(Fu Hanxi - 15ac941)*
- support filter by sdkconfig *(Fu Hanxi - a2e727f)*
- support idf-ci test run --collect-only *(Fu Hanxi - b3cd106)*
- support get_all_apps *(Fu Hanxi - e608d57)*
- support `idf-ci test run` *(Fu Hanxi - 3ec6894)*
- support build with modified files and components *(Fu Hanxi - a548952)*
- support idf-ci commands with --profiles *(Fu Hanxi - c2e4f97)*
- support parallel count in build command *(Fu Hanxi - 175b32e)*
- support build with profiles *(Fu Hanxi - 9addf0e)*
- support `get_pytest_cases` *(Fu Hanxi - 2a5c1c4)*
- support load multiple profile *(Fu Hanxi - e4eb9ea)*
- support `idf-ci ci-profile init`, split cli into multi modules *(Fu Hanxi - 84e9fa6)*
- support configure ignored file extensions while getting modified components *(Fu Hanxi - 8be9782)*
- support configure mapping modified file to modified component *(Fu Hanxi - ff6accf)*

### 🐛 Bug Fixes

- **build**: include all sub packages and template files *(Fu Hanxi - 4e57a4d)*
- log instead of mark cases skip while collecting *(Fu Hanxi - 3865e50)*
- load only built apps *(Fu Hanxi - a2a5304)*
- small fixes on undefined args *(Fu Hanxi - 291a3ff)*
- windows paths *(Fu Hanxi - 13e87f6)*

### 📖 Documentation

- init documentation with api references *(Fu Hanxi - 77660d6)*

### 🔧 Code Refactoring

- move cli structure *(Fu Hanxi - 92704cc)*

### 🏗️ Changes

- rename test-related and non-test-related with --only prefix *(Fu Hanxi - 31b9720)*

---

<div style="text-align: center;">
    <small>
        <b>
            <a href="https://www.github.com/espressif/cz-plugin-espressif">Commitizen Espressif plugin</a>
        </b>
    <br>
        <sup><a href="https://www.espressif.com">Espressif Systems CO LTD. (2025)</a><sup>
    </small>
</div>
