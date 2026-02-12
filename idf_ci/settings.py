# SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import re
import typing as t
from contextvars import ContextVar
from pathlib import Path

from idf_build_apps import App, json_list_files_to_apps
from idf_build_apps.constants import BuildStatus
from pydantic import BaseModel, model_validator
from pydantic_settings import (
    BaseSettings as _BaseSettings,
)
from pydantic_settings import (
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from tomlkit import load

from idf_ci._compat import PathLike

logger = logging.getLogger(__name__)


class BaseSettings(_BaseSettings):
    model_config = SettingsConfigDict(
        use_attribute_docstrings=True,
    )


class TomlConfigSettingsSource(InitSettingsSource):
    """A source class that loads variables from a TOML file"""

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        toml_file: PathLike | None = Path(''),
    ):
        self.toml_file_path = pick_toml_file(toml_file)
        self.toml_data = self._read_file(self.toml_file_path)
        super().__init__(settings_cls, self.toml_data)

    def _read_file(self, path: Path | None) -> dict[str, t.Any]:
        if not path or not path.is_file():
            return {}

        with open(path) as f:
            return load(f)


def pick_toml_file(provided: PathLike | None, filename: str = '.idf_ci.toml') -> Path | None:
    """Pick a file path to use.

    If a file path is provided, use it. Otherwise, search up the directory tree for a
    file with the given name.

    :param provided: Explicit path provided when instantiating this function.
    :param filename: Name of the file to search for.
    """
    if provided:
        provided_p = Path(provided)
        if provided_p.is_file():
            fp = provided_p.resolve()
            logger.debug(f'Loading config file: {fp}')
            return fp

    rv = Path.cwd()
    while len(rv.parts) > 1:
        fp = rv / filename
        if fp.is_file():
            logger.debug(f'Loading config file: {fp}')
            return fp

        rv = rv.parent

    return None


class CliOverridesSettingsSource(InitSettingsSource):
    """A source class that loads variables from an in-memory dict for CLI overrides"""

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        overrides: dict[str, t.Any] | None = None,
    ):
        self.overrides = overrides or {}
        super().__init__(settings_cls, self.overrides)


class S3ArtifactConfig(BaseModel):
    bucket: str
    """S3 bucket used to store artifacts for this type."""

    is_public: bool = False
    """Whether the S3 bucket is public. Requires ListBucket and GetObject permissions."""

    zip_first: bool = False
    """Whether to create zip files before uploading to S3.

    If False, files are uploaded individually without zipping.
    """

    base_dir_pattern: str | None = None
    """Glob pattern for base directories to create zip files from.

    The pattern should match directories only (for example, ``**/build*/``). If not set,
    the current folder is used as the base directory.
    """

    patterns: list[str] = ['**/*']
    """Glob patterns (relative to each base directory) for files to include.

    If empty or omitted, all files under the base directory are included.
    """

    if_clause: str | None = None
    """Optional boolean expression to decide whether this artifact type is enabled."""


class ArtifactSettingsS3(BaseModel):
    enable: bool = False
    """Whether to enable S3 artifact upload/download and presigned URL generation."""

    configs: dict[str, S3ArtifactConfig] | dict[str, dict[str, t.Any]] = {
        'debug': {
            'bucket': 'idf-artifacts',
            'base_dir_pattern': '**/build*/',
            'patterns': [
                'bootloader/*.map',
                'bootloader/*.elf',
                '*.map',
                '*.elf',
                'build.log',  # build_log_filename
            ],
        },
        'flash': {
            'bucket': 'idf-artifacts',
            'base_dir_pattern': '**/build*/',
            'patterns': [
                'bootloader/*.bin',
                '*.bin',
                'partition_table/*.bin',
                'flasher_args.json',
                'flash_project_args',
                'config/sdkconfig.json',
                'sdkconfig',
                'project_description.json',
            ],
        },
    }
    """Dictionary mapping artifact types to their S3 upload configuration.

    Depending on the corresponding :class:`S3ArtifactConfig`'s ``zip_first`` setting,
    each matching base directory either produces a ``<artifact_type>.zip`` that is
    uploaded to the configured bucket, or uploads the matching files directly without
    creating a zip archive.
    """

    @model_validator(mode='after')
    def validate_configs(self):
        if isinstance(self.configs, dict):
            self.configs = {
                key: S3ArtifactConfig.model_validate(value) if isinstance(value, dict) else value
                for key, value in self.configs.items()
            }
        return self


class ArtifactSettingsNative(BaseModel):
    enable: bool = True
    """Whether to use GitLab native artifacts."""

    build_job_filepatterns: list[str] = [
        # debug
        '**/build*/bootloader/*.map',
        '**/build*/bootloader/*.elf',
        '**/build*/*.map',
        '**/build*/*.elf',
        # flash
        '**/build*/bootloader/*.bin',
        '**/build*/*.bin',
        '**/build*/partition_table/*.bin',
        '**/build*/flasher_args.json',
        '**/build*/flash_project_args',
        '**/build*/config/sdkconfig.json',
        '**/build*/sdkconfig',
        '**/build*/project_description.json',
        # info
        '**/build*/build.log',  # build_log_filename
        'app_info_*.txt',  # collect_app_info_filename
        'build_summary_*.xml',  # junitxml
    ]
    """List of glob patterns for CI build jobs artifacts to collect."""

    test_job_filepatterns: list[str] = [
        'pytest-embedded/',
        'XUNIT_RESULT*.xml',
    ]
    """List of glob patterns for CI test jobs artifacts to collect."""


class ArtifactSettings(BaseModel):
    s3: ArtifactSettingsS3 = ArtifactSettingsS3()
    """S3 artifact upload settings."""

    native: ArtifactSettingsNative = ArtifactSettingsNative()
    """GitLab native artifact settings."""


class BuildPipelineSettings(BaseModel):
    workflow_name: str = 'Build Child Pipeline'
    """Name for the GitLab CI workflow."""

    presigned_json_job_name: str = 'generate_presigned_json'
    """Name of the job within the child pipeline that creates presigned.json."""

    job_template_name: str = '.default_build_settings'
    """Default template name for CI build jobs."""

    job_image: str = 'espressif/idf:latest'
    """Docker image to use for build jobs."""

    job_stage: str = 'build'
    """Default stage for build jobs in the pipeline."""

    job_template_jinja: str = """
{{ settings.gitlab.build_pipeline.job_template_name }}:
  stage: "{{ settings.gitlab.build_pipeline.job_stage }}"
  tags: {{ settings.gitlab.build_pipeline.job_tags }}
  image: "{{ settings.gitlab.build_pipeline.job_image }}"
  timeout: "1h"
  artifacts:
    paths:
    {%- for path in settings.gitlab.artifacts.native.build_job_filepatterns %}
      - "{{ path }}"
    {%- endfor %}
    expire_in: "1 week"
    when: "always"
  before_script:
    - pip install -U idf-ci
  script:
    - idf-ci build run
      --parallel-count ${CI_NODE_TOTAL:-1}
      --parallel-index ${CI_NODE_INDEX:-1}
""".strip()
    """Default template for CI build jobs."""

    job_tags: list[str] = ['build']
    """List of tags for CI build jobs."""

    runs_per_job: int = 60
    """Maximum number of apps to build in a single job."""

    parent_pipeline_job_suffix: str = ''
    """Suffix to append to parent pipeline job names when referencing them."""

    jobs_jinja: str = """
{%- if test_related_apps_count > 0 %}
build_test_related_apps:
  extends: "{{ settings.gitlab.build_pipeline.job_template_name }}"
{%- if test_related_parallel_count > 1 %}
  parallel: {{ test_related_parallel_count }}
{%- endif %}
  needs:
    - pipeline: "$PARENT_PIPELINE_ID"
      job: "generate_build_child_pipeline{{ settings.gitlab.build_pipeline.parent_pipeline_job_suffix }}"
    - pipeline: "$PARENT_PIPELINE_ID"
      job: "pipeline_variables{{ settings.gitlab.build_pipeline.parent_pipeline_job_suffix }}"
  variables:
    IDF_CI_BUILD_ONLY_TEST_RELATED_APPS: "1"

{% endif %}
{%- if non_test_related_apps_count > 0 %}
build_non_test_related_apps:
  extends: "{{ settings.gitlab.build_pipeline.job_template_name }}"
{%- if non_test_related_parallel_count > 1 %}
  parallel: {{ non_test_related_parallel_count }}
{%- endif %}
  needs:
    - pipeline: "$PARENT_PIPELINE_ID"
      job: "generate_build_child_pipeline{{ settings.gitlab.build_pipeline.parent_pipeline_job_suffix }}"
    - pipeline: "$PARENT_PIPELINE_ID"
      job: "pipeline_variables{{ settings.gitlab.build_pipeline.parent_pipeline_job_suffix }}"
  variables:
    IDF_CI_BUILD_ONLY_NON_TEST_RELATED_APPS: "1"

{% endif %}
""".strip()
    """Jinja2 template for build jobs configuration."""

    pre_yaml_jinja: str = ''
    """yaml content to be injected before the yaml template."""

    yaml_jinja: str = """
{{ settings.gitlab.build_pipeline.pre_yaml_jinja }}

workflow:
  name: "{{ settings.gitlab.build_pipeline.workflow_name }}"
  rules:
    - when: "always"

{% if settings.gitlab.build_pipeline.job_template_jinja %}
{{ job_template }}
{%- endif %}

{{ jobs }}

{%- if test_related_apps_count > 0 %}
generate_test_child_pipeline:
  extends: "{{ settings.gitlab.build_pipeline.job_template_name }}"
  needs:
    - "build_test_related_apps"
  artifacts:
    paths:
      - "{{ settings.gitlab.test_pipeline.yaml_filename }}"
  script:
    - idf-ci
      --config 'gitlab.test_pipeline.job_image="{{ settings.gitlab.test_pipeline.job_image }}"'
      gitlab test-child-pipeline

test-child-pipeline:
  stage: ".post"
  needs:
    - "generate_test_child_pipeline"
  variables:
    PARENT_PIPELINE_ID: "$CI_PIPELINE_ID"
  trigger:
    include:
      - artifact: "{{ settings.gitlab.test_pipeline.yaml_filename }}"
        job: "generate_test_child_pipeline"
    strategy: "depend"
{%- endif %}
""".strip()
    """Jinja2 template for the build child pipeline YAML content."""

    yaml_filename: str = 'build_child_pipeline.yml'
    """Filename for the build child pipeline YAML file."""


class TestPipelineSettings(BuildPipelineSettings):
    workflow_name: str = 'Test Child Pipeline'
    """Name for the GitLab CI workflow."""

    job_template_name: str = '.default_test_settings'
    """Default template name for CI test jobs."""

    job_stage: str = 'test'
    """Default stage for test jobs in the pipeline."""

    job_image: str = 'python:3-slim'
    """Docker image to use for test jobs."""

    job_template_jinja: str = """
{{ settings.gitlab.test_pipeline.job_template_name }}:
  stage: "{{ settings.gitlab.test_pipeline.job_stage }}"
  image: "{{ settings.gitlab.test_pipeline.job_image }}"
  timeout: "1h"
  artifacts:
    paths:
    {%- for path in settings.gitlab.artifacts.native.test_job_filepatterns %}
      - "{{ path }}"
    {%- endfor %}
    expire_in: "1 week"
    when: "always"
  variables:
    PYTEST_EXTRA_FLAGS: ""
  needs:
    - pipeline: "$PARENT_PIPELINE_ID"
      job: "build_test_related_apps"
  before_script:
    - pip install -U idf-ci
  script:
    - eval pytest $nodes
      --parallel-count ${CI_NODE_TOTAL:-1}
      --parallel-index ${CI_NODE_INDEX:-1}
      --junitxml "XUNIT_RESULT_${CI_JOB_NAME_SLUG}.xml"
      ${PYTEST_EXTRA_FLAGS}
""".strip()
    """Default template for CI test jobs."""

    job_tags: list[str] = []
    """Unused. tags are set by test cases."""

    runs_per_job: int = 30
    """Maximum number of test cases to run in a single job."""

    jobs_jinja: str = """
{% for job in jobs %}
{{ job['name'] }}:
  extends:
    - "{{ settings.gitlab.test_pipeline.job_template_name }}"
    {%- for extra_extend in job.get('extra_extends', []) %}
    - "{{ extra_extend }}"
    {%- endfor %}
  tags: {{ job['tags'] }}
{%- if job['parallel_count'] > 1 %}
  parallel: {{ job['parallel_count'] }}
{%- endif %}
  variables:
    nodes: {{ job['nodes'] }}
{% endfor %}
""".strip()
    """Jinja2 template for test jobs configuration."""

    yaml_jinja: str = """
{{ settings.gitlab.test_pipeline.pre_yaml_jinja }}

workflow:
  name: "{{ settings.gitlab.test_pipeline.workflow_name }}"
  rules:
    - when: "always"

{% if settings.gitlab.test_pipeline.job_template_jinja %}
{{ default_template }}
{%- endif %}

{{ jobs }}
""".strip()
    """Jinja2 template for the test child pipeline YAML content."""

    yaml_filename: str = 'test_child_pipeline.yml'
    """Filename for the test child pipeline YAML file."""


class GitlabSettings(BaseModel):
    project: str = 'espressif/esp-idf'
    """GitLab project path in the format 'owner/repo'."""

    known_failure_cases_bucket_name: str = 'ignore-test-result-files'
    """Bucket name for storing known failure cases."""

    artifacts: ArtifactSettings = ArtifactSettings()

    build_pipeline: BuildPipelineSettings = BuildPipelineSettings()

    test_pipeline: TestPipelineSettings = TestPipelineSettings()


class CiSettings(BaseSettings):
    CONFIG_FILE_PATH: t.ClassVar[Path | None] = None
    """Path to the configuration file to be used (class variable)."""

    CLI_OVERRIDES: t.ClassVar[dict[str, t.Any]] = {}
    """Inline CLI overrides (class variable)."""

    # --- instance variables below ---

    component_mapping_regexes: list[str] = [
        '/components/(.+?)/',
        '/common_components/(.+?)/',
    ]
    """List of regex patterns to extract component names from file paths."""

    extend_component_mapping_regexes: list[str] = []
    """Additional component mapping regex patterns to extend the default list."""

    component_mapping_exclude_regexes: list[str] = [
        r'/test_apps/',
    ]
    """List of regex patterns to exclude certain paths from component mapping."""

    component_ignored_file_extensions: list[str] = [
        '.md',
        '.rst',
        '.yaml',
        '.yml',
        '.py',
    ]
    """File extensions to ignore when mapping files to components."""

    extend_component_ignored_file_extensions: list[str] = []
    """Additional file extensions to ignore."""

    # build related settings
    built_app_list_filepatterns: list[str] = ['app_info_*.txt']
    """Glob patterns for files containing built app information."""

    collected_test_related_apps_filepath: str = 'test_related_apps.txt'
    """Path to file containing test-related apps."""

    collected_non_test_related_apps_filepath: str = 'non_test_related_apps.txt'
    """Path to file containing non-test-related apps."""

    preserve_test_related_apps: bool = True
    """Whether to preserve test-related apps."""

    preserve_non_test_related_apps: bool = True
    """Whether to preserve non-test-related apps."""

    extra_default_build_targets: list[str] = []
    """Additional build targets to include by default."""

    exclude_dirs: list[str] = []
    """Directories to ignore when searching for apps."""

    # env vars
    ci_detection_envs: list[str] = [
        'CI',
        'GITHUB_ACTIONS',
        'CIRCLECI',
        'TRAVIS',
        'JENKINS_URL',
        'DRONE',
        'APPVEYOR',
        'BITBUCKET_COMMIT',
        'SEMAPHORE',
        'TEAMCITY_VERSION',
    ]
    """Environment variables used to detect if running in CI."""

    local_runtime_envs: dict[str, t.Any] = {}
    """Environment variables to set in local development."""

    ci_runtime_envs: dict[str, t.Any] = {}
    """Environment variables to set in CI environment."""

    # gitlab subsection
    gitlab: GitlabSettings = GitlabSettings()
    """GitLab-specific settings."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],  # type: ignore[override]
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            # Precedence: CLI overrides > init kwargs > TOML file > defaults
            CliOverridesSettingsSource(settings_cls, getattr(cls, 'CLI_OVERRIDES', None)),
            init_settings,
            TomlConfigSettingsSource(
                settings_cls, cls.CONFIG_FILE_PATH if cls.CONFIG_FILE_PATH is not None else '.idf_ci.toml'
            ),
        )

    def model_post_init(self, __context: t.Any) -> None:
        runtime_envs = self.ci_runtime_envs if self.is_in_ci else self.local_runtime_envs

        for key, value in runtime_envs.items():
            os.environ[key] = str(value)
            logger.debug('Set local env var: %s=%s', key, value)

    @property
    def is_in_ci(self) -> bool:
        """Check if the code is running in a CI environment.

        :returns: True if in CI environment, False otherwise
        """
        return any(os.getenv(env) is not None for env in self.ci_detection_envs)

    @property
    def all_component_mapping_regexes(self) -> set[re.Pattern]:
        """Get all component mapping regexes as compiled pattern objects.

        :returns: Set of compiled regex patterns
        """
        return {re.compile(regex) for regex in self.component_mapping_regexes + self.extend_component_mapping_regexes}

    @property
    def all_component_mapping_exclude_regexes(self) -> set[re.Pattern]:
        """Get all component mapping exclude regexes as compiled pattern objects.

        :returns: Set of compiled regex patterns
        """
        return {re.compile(regex) for regex in self.component_mapping_exclude_regexes}

    def get_modified_components(self, modified_files: t.Iterable[str]) -> set[str]:
        """Get the set of components that have been modified based on the provided files.

        :param modified_files: Iterable of file paths that have been modified

        :returns: Set of component names that have been modified
        """
        modified_components = set()

        for modified_file in modified_files:
            file_path = Path(modified_file)
            if (
                file_path.suffix
                in self.component_ignored_file_extensions + self.extend_component_ignored_file_extensions
            ):
                continue

            # always use absolute path as posix string
            # Path.resolve return relative path when file does not exist. so use os.path.abspath
            abs_path = Path(os.path.abspath(modified_file)).as_posix()

            for regex in self.all_component_mapping_regexes:
                match = regex.search(abs_path)
                if match:
                    for exclude_regex in self.all_component_mapping_exclude_regexes:
                        if exclude_regex.search(abs_path):
                            logger.debug(f'Excluding {abs_path} from component mapping')
                            break
                    else:
                        modified_components.add(match.group(1))
                        break

        return modified_components

    @classmethod
    def read_apps_from_files(cls, filepaths: t.Sequence[PathLike]) -> list[App] | None:
        """Helper method to read apps from files.

        :param filepaths: List of file paths to read

        :returns: List of App objects read from the files, or None if no files found
        """
        valid_filepaths = []
        for filepath in filepaths:
            if os.path.isfile(filepath):
                valid_filepaths.append(str(filepath))
            else:
                logger.debug(f'No file found: {filepath}')

        if not valid_filepaths:
            return None

        return json_list_files_to_apps(valid_filepaths)

    @classmethod
    def read_apps_from_filepatterns(cls, patterns: list[str]) -> list[App] | None:
        """Helper method to read apps from files matching given patterns.

        :param patterns: List of file patterns to search for

        :returns: List of App objects read from the files, or None if no files found
        """
        found_files = []
        for filepattern in patterns:
            found_files.extend([str(p) for p in (Path('.').glob(filepattern))])

        if not found_files:
            logger.debug(f'No files found for patterns: {patterns}')
            return None

        apps = json_list_files_to_apps(found_files)

        if not apps:
            logger.warning(f'No apps found for patterns: {patterns}, returning empty list')

        return apps

    def get_built_apps_list(self) -> list[App] | None:
        """Get the list of successfully built applications from the app info files.

        :returns: List of App objects representing successfully built applications, or
            None if no files found
        """
        # Read apps from files
        apps = self.read_apps_from_filepatterns(self.built_app_list_filepatterns)

        if apps is None:
            return None

        # Filter for successful builds
        built_apps = [app for app in apps if app.build_status == BuildStatus.SUCCESS]

        return built_apps


_ci_settings_context: ContextVar['CiSettings'] = ContextVar('ci_settings', default=CiSettings())


def get_ci_settings() -> 'CiSettings':
    """Get the current CiSettings instance from the context."""
    return _ci_settings_context.get()


def _refresh_ci_settings(
    config_file: PathLike | None = None,
    config_overrides: dict[str, t.Any] | None = None,
) -> 'CiSettings':
    """Refresh the CiSettings instance in the context. shall be called only by CLI entry point."""
    if config_file:
        logger.debug(f'Loading from config file `{config_file}`...')
        CiSettings.CONFIG_FILE_PATH = Path(config_file)

    if config_overrides:
        logger.debug('Loading from cli overrides...')
        CiSettings.CLI_OVERRIDES = config_overrides

    settings = CiSettings()
    _ci_settings_context.set(settings)
    return settings
