# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import re
import sys
import typing as t
from pathlib import Path

from idf_build_apps import App, json_to_app
from idf_build_apps.constants import BuildStatus
from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)

from idf_ci._compat import PathLike

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

        if sys.version_info < (3, 11):
            from tomlkit import load

            with open(path) as f:
                return load(f)
        else:
            import tomllib

            with open(path, 'rb') as f:
                return tomllib.load(f)

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


class GitlabSettings(BaseSettings):
    project: str = 'espressif/esp-idf'
    debug_artifacts_filepatterns: t.List[str] = [
        '**/build*/bootloader/*.map',
        '**/build*/bootloader/*.elf',
        '**/build*/*.map',
        '**/build*/*.elf',
        '**/build*/build.log',  # build_log_filename
    ]
    flash_artifacts_filepatterns: t.List[str] = [
        '**/build*/bootloader/*.bin',
        '**/build*/*.bin',
        '**/build*/partition_table/*.bin',
        '**/build*/flasher_args.json',
        '**/build*/flash_project_args',
        '**/build*/config/sdkconfig.json',
        '**/build*/sdkconfig',
        '**/build*/project_description.json',
    ]
    metrics_artifacts_filepatterns: t.List[str] = [
        '**/build*/size.json',  # size_json_filename
    ]
    # TODO use it in ci job
    ci_artifacts_filepatterns: t.List[str] = [
        'app_info_*.txt',  # collect_app_info_filename
        'presigned_urls.json',
        'build_summary_*.xml',  # junitxml
        'pipeline.env',  # pipeline.env
    ]

    build_apps_count_per_job: int = 60
    build_jobs_jinja_template: str = """
build_apps:
  extends:
    - .default_build_template
{%- if parallel_count > 1 %}
  parallel: {{ parallel_count }}
{%- endif %}
  timeout: 1h
  variables:
    IDF_CCACHE_ENABLE: "1"
  needs:
    - pipeline: $PARENT_PIPELINE_ID
      job: generate_build_child_pipeline
  script:
    - idf-ci build run
""".strip()
    build_child_pipeline_yaml_jinja_template: str = """
{{ build_jobs_yaml }}

{{ generate_test_child_pipeline_yaml }}

{{ test_child_pipeline_job }}
""".strip()
    build_child_pipeline_yaml_filename: str = 'build_child_pipeline.yml'


class CiSettings(BaseSettings):
    CONFIG_FILE_PATH: t.ClassVar[t.Optional[Path]] = None

    component_mapping_regexes: t.List[str] = [
        '/components/(.+)/',
        '/common_components/(.+)/',
    ]
    extend_component_mapping_regexes: t.List[str] = []

    component_ignored_file_extensions: t.List[str] = [
        '.md',
        '.rst',
        '.yaml',
        '.yml',
        '.py',
    ]
    extend_component_ignored_file_extensions: t.List[str] = []

    # build related settings
    built_app_list_filepatterns: t.List[str] = ['app_info_*.txt']

    collected_test_related_apps_filepath: str = 'test_related_apps.txt'
    collected_non_test_related_apps_filepath: str = 'non_test_related_apps.txt'

    preserve_test_related_apps: bool = True
    preserve_non_test_related_apps: bool = True

    extra_default_build_targets: t.List[str] = []

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
    local_runtime_envs: t.Dict[str, t.Any] = {}
    ci_runtime_envs: t.Dict[str, t.Any] = {}

    # gitlab subsection
    gitlab: GitlabSettings = GitlabSettings()

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
    def _read_apps_from_file(cls, filename: PathLike) -> t.Optional[t.List[App]]:
        """Helper method to read apps from a file.

        :param filename: Name of the file to read

        :returns: List of App objects read from the file, or None if no file found
        """
        if not Path(filename).is_file():
            logger.debug(f'No file found: {filename}')
            return None

        apps: t.List[App] = []
        with open(filename) as fr:
            for line in fr.readlines():
                line = line.strip()
                if not line:
                    continue

                app = json_to_app(line)
                apps.append(app)
                logger.debug('App found: %s', app.build_path)

        if not apps:
            logger.warning(f'No apps found in file: {filename}, returning empty list')

        return apps

    @classmethod
    def _read_apps_from_filepatterns(cls, patterns: t.List[str]) -> t.Optional[t.List[App]]:
        """Helper method to read apps from files matching given patterns.

        :param patterns: List of file patterns to search for

        :returns: List of App objects read from the files, or None if no files found
        """
        found_files = []
        for filepattern in patterns:
            found_files.extend(list(Path('.').glob(filepattern)))

        if not found_files:
            logger.debug(f'No files found for patterns: {patterns}')
            return None

        apps: t.List[App] = []
        for filepattern in patterns:
            for filepath in Path('.').glob(filepattern):
                apps.extend(cls._read_apps_from_file(filepath) or [])

        if not apps:
            logger.warning(f'No apps found for patterns: {patterns}, returning empty list')

        return apps

    def get_collected_apps_list(self) -> t.Tuple[t.Optional[t.List[App]], t.Optional[t.List[App]]]:
        """Get the lists of collected test-related and non-test-related applications.

        :returns: A tuple containing (test_related_apps, non_test_related_apps), or None
            if no files found
        """
        # Read apps from files
        test_related_apps = self._read_apps_from_file(self.collected_test_related_apps_filepath)
        non_test_related_apps = self._read_apps_from_file(self.collected_non_test_related_apps_filepath)

        # either all are None or all are lists
        if test_related_apps is None and non_test_related_apps is None:
            return None, None

        return test_related_apps or [], non_test_related_apps or []

    def get_built_apps_list(self) -> t.Optional[t.List[App]]:
        """Get the list of successfully built applications from the app info files.

        :returns: List of App objects representing successfully built applications, or
            None if no files found
        """
        # Read apps from files
        apps = self._read_apps_from_filepatterns(self.built_app_list_filepatterns)

        if apps is None:
            return None

        # Filter for successful builds
        built_apps = [app for app in apps if app.build_status == BuildStatus.SUCCESS]

        return built_apps
