# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import re
import sys
import typing as t
from pathlib import Path

from idf_build_apps import App, json_list_files_to_apps
from idf_build_apps.constants import BuildStatus
from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)
from tomlkit import load

from idf_ci._compat import PathLike, TypedDict

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired


logger = logging.getLogger(__name__)


class TomlConfigSettingsSource(InitSettingsSource):
    """A source class that loads variables from a TOML file"""

    def __init__(
        self,
        settings_cls: t.Type[BaseSettings],
        toml_file: t.Optional[PathLike] = Path(''),
    ):
        self.toml_file_path = self._pick_toml_file(
            toml_file,
            '.idf_ci.toml',
        )
        self.toml_data = self._read_file(self.toml_file_path)
        super().__init__(settings_cls, self.toml_data)

    def _read_file(self, path: t.Optional[Path]) -> t.Dict[str, t.Any]:
        if not path or not path.is_file():
            return {}

        with open(path) as f:
            return load(f)

    @staticmethod
    def _pick_toml_file(provided: t.Optional[PathLike], filename: str) -> t.Optional[Path]:
        """Pick a file path to use.

        If a file path is provided, use it. Otherwise, search up the directory tree for
        a file with the given name.

        :param provided: Explicit path provided when instantiating this class.
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


class S3FilePatternConfig(TypedDict):
    bucket: str
    patterns: t.List[str]
    if_clause: NotRequired[str]
    """List of glob patterns for files to collect."""


class ArtifactSettings(BaseSettings):
    ### in s3 buckets ###
    s3: t.Dict[str, S3FilePatternConfig] = {
        'debug': {
            'bucket': 'idf-artifacts',
            'patterns': [
                '**/build*/bootloader/*.map',
                '**/build*/bootloader/*.elf',
                '**/build*/*.map',
                '**/build*/*.elf',
                '**/build*/build.log',  # build_log_filename
            ],
        },
        'flash': {
            'bucket': 'idf-artifacts',
            'patterns': [
                '**/build*/bootloader/*.bin',
                '**/build*/*.bin',
                '**/build*/partition_table/*.bin',
                '**/build*/flasher_args.json',
                '**/build*/flash_project_args',
                '**/build*/config/sdkconfig.json',
                '**/build*/sdkconfig',
                '**/build*/project_description.json',
            ],
        },
    }
    """Dictionary mapping artifact types to their bucket and file patterns."""

    ### not in s3 buckets ###

    build_job_filepatterns: t.List[str] = [
        'app_info_*.txt',  # collect_app_info_filename
        'build_summary_*.xml',  # junitxml
    ]
    """List of glob patterns for CI build jobs artifacts to collect."""

    test_job_filepatterns: t.List[str] = [
        'pytest-embedded/',
        'XUNIT_RESULT*.xml',
    ]
    """List of glob patterns for CI test jobs artifacts to collect."""

    @property
    def available_s3_types(self) -> t.List[str]:
        """Get list of available S3 artifact types.

        :returns: List of artifact type names
        """
        return sorted(self.s3.keys())


class BuildPipelineSettings(BaseSettings):
    workflow_name: str = 'Build Child Pipeline'
    """Name for the GitLab CI workflow."""

    job_template_name: str = '.default_build_settings'
    """Default template name for CI build jobs."""

    job_template_jinja: str = """
{{ settings.gitlab.build_pipeline.job_template_name }}:
  stage: build
  tags: {{ settings.gitlab.build_pipeline.job_tags }}
  timeout: 1h
  artifacts:
    paths:
    {%- for path in settings.gitlab.artifacts.build_job_filepatterns %}
      - {{ path }}
    {%- endfor %}
    expire_in: 1 week
    when: always
  script:
    - idf-ci build run
      --parallel-count ${CI_NODE_TOTAL:-1}
      --parallel-index ${CI_NODE_INDEX:-1}
""".strip()
    """Default template for CI test jobs."""

    job_tags: t.List[str] = ['build']
    """List of tags for CI build jobs."""

    runs_per_job: int = 60
    """Maximum number of apps to build in a single job."""

    jobs_jinja: str = """
build_apps:
  extends: {{ settings.gitlab.build_pipeline.job_template_name }}
{%- if parallel_count > 1 %}
  parallel: {{ parallel_count }}
{%- endif %}
  needs:
    - pipeline: $PARENT_PIPELINE_ID
      job: generate_build_child_pipeline
    - pipeline: $PARENT_PIPELINE_ID
      job: pipeline_variables
""".strip()
    """Jinja2 template for build jobs configuration."""

    pre_yaml_jinja: str = ''
    """yaml content to be injected before the yaml template."""

    yaml_jinja: str = """
{{ settings.gitlab.build_pipeline.pre_yaml_jinja }}

workflow:
  name: {{ settings.gitlab.build_pipeline.workflow_name }}
  rules:
    - when: always

{%- if settings.gitlab.build_pipeline.job_template_jinja %}
{{ job_template }}
{%- endif %}

{{ jobs }}

generate_test_child_pipeline:
  extends: {{ settings.gitlab.build_pipeline.job_template_name }}
  needs:
    - build_apps
  artifacts:
    paths:
      - {{ settings.gitlab.test_pipeline.yaml_filename }}
  script:
    - idf-ci gitlab test-child-pipeline

test-child-pipeline:
  stage: .post
  needs:
    - generate_test_child_pipeline
  variables:
    PARENT_PIPELINE_ID: $PARENT_PIPELINE_ID
  trigger:
    include:
      - artifact: {{ settings.gitlab.test_pipeline.yaml_filename }}
        job: generate_test_child_pipeline
    strategy: depend
""".strip()
    """Jinja2 template for the build child pipeline YAML content."""

    yaml_filename: str = 'build_child_pipeline.yml'
    """Filename for the build child pipeline YAML file."""


class TestPipelineSettings(BuildPipelineSettings):
    workflow_name: str = 'Test Child Pipeline'
    """Name for the GitLab CI workflow."""

    job_template_name: str = '.default_test_settings'
    """Default template name for CI test jobs."""

    job_tags: t.List[str] = []
    """Unused. tags are set by test cases."""

    job_template_jinja: str = """
{{ settings.gitlab.test_pipeline.job_template_name }}:
  stage: test
  timeout: 1h
  artifacts:
    paths:
    {%- for path in settings.gitlab.artifacts.test_job_filepatterns %}
      - {{ path }}
    {%- endfor %}
    expire_in: 1 week
    when: always
  variables:
    PYTEST_EXTRA_FLAGS: ""
  script:
    - pytest ${nodes}
      --parallel-count ${CI_NODE_TOTAL:-1}
      --parallel-index ${CI_NODE_INDEX:-1}
      --junitxml XUNIT_RESULT_${CI_JOB_NAME_SLUG}.xml
      ${PYTEST_EXTRA_FLAGS}
""".strip()
    """Default template for CI test jobs."""

    runs_per_job: int = 30
    """Maximum number of test cases to run in a single job."""

    jobs_jinja: str = """
{% for job in jobs %}
{{ job['name'] }}:
  extends:
    - {{ settings.gitlab.test_pipeline.job_template_name }}
    {%- for extra_extend in job.get('extra_extends', []) %}
    - {{ extra_extend }}
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
  name: {{ settings.gitlab.test_pipeline.workflow_name }}
  rules:
    - when: always

{%- if settings.gitlab.test_pipeline.job_template_jinja %}
{{ default_template }}
{%- endif %}

{{ jobs }}
""".strip()
    """Jinja2 template for the test child pipeline YAML content."""

    yaml_filename: str = 'test_child_pipeline.yml'
    """Filename for the test child pipeline YAML file."""


class GitlabSettings(BaseSettings):
    project: str = 'espressif/esp-idf'
    """GitLab project path in the format 'owner/repo'."""

    known_failure_cases_bucket_name: str = 'ignore-test-result-files'
    """Bucket name for storing known failure cases."""

    artifacts: ArtifactSettings = ArtifactSettings()

    build_pipeline: BuildPipelineSettings = BuildPipelineSettings()

    test_pipeline: TestPipelineSettings = TestPipelineSettings()


class CiSettings(BaseSettings):
    CONFIG_FILE_PATH: t.ClassVar[t.Optional[Path]] = None
    """Path to the configuration file to be used (class variable)."""

    component_mapping_regexes: t.List[str] = [
        '/components/(.+)/',
        '/common_components/(.+)/',
    ]
    """List of regex patterns to extract component names from file paths."""

    extend_component_mapping_regexes: t.List[str] = []
    """Additional component mapping regex patterns to extend the default list."""

    component_ignored_file_extensions: t.List[str] = [
        '.md',
        '.rst',
        '.yaml',
        '.yml',
        '.py',
    ]
    """File extensions to ignore when mapping files to components."""

    extend_component_ignored_file_extensions: t.List[str] = []
    """Additional file extensions to ignore."""

    # build related settings
    built_app_list_filepatterns: t.List[str] = ['app_info_*.txt']
    """Glob patterns for files containing built app information."""

    collected_test_related_apps_filepath: str = 'test_related_apps.txt'
    """Path to file containing test-related apps."""

    collected_non_test_related_apps_filepath: str = 'non_test_related_apps.txt'
    """Path to file containing non-test-related apps."""

    preserve_test_related_apps: bool = True
    """Whether to preserve test-related apps."""

    preserve_non_test_related_apps: bool = True
    """Whether to preserve non-test-related apps."""

    extra_default_build_targets: t.List[str] = []
    """Additional build targets to include by default."""

    # env vars
    ci_detection_envs: t.List[str] = [
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

    local_runtime_envs: t.Dict[str, t.Any] = {}
    """Environment variables to set in local development."""

    ci_runtime_envs: t.Dict[str, t.Any] = {}
    """Environment variables to set in CI environment."""

    # gitlab subsection
    gitlab: GitlabSettings = GitlabSettings()
    """GitLab-specific settings."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> t.Tuple[PydanticBaseSettingsSource, ...]:
        return (
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
    def all_component_mapping_regexes(self) -> t.Set[re.Pattern]:
        """Get all component mapping regexes as compiled pattern objects.

        :returns: Set of compiled regex patterns
        """
        return {re.compile(regex) for regex in self.component_mapping_regexes + self.extend_component_mapping_regexes}

    def get_modified_components(self, modified_files: t.Iterable[str]) -> t.Set[str]:
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
                    modified_components.add(match.group(1))
                    break

        return modified_components

    @classmethod
    def read_apps_from_files(cls, filepaths: t.Sequence[PathLike]) -> t.Optional[t.List[App]]:
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
    def read_apps_from_filepatterns(cls, patterns: t.List[str]) -> t.Optional[t.List[App]]:
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

    def get_built_apps_list(self) -> t.Optional[t.List[App]]:
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
