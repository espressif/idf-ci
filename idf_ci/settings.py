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
    """
    A source class that loads variables from a TOML file
    """

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
        """
        Pick a file path to use. If a file path is provided, use it. Otherwise, search up the directory tree for a
        file with the given name.

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
    preserve_test_related_apps: bool = True
    preserve_non_test_related_apps: bool = False

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> t.Tuple[PydanticBaseSettingsSource, ...]:
        sources: t.Tuple[PydanticBaseSettingsSource, ...] = (init_settings,)
        if cls.CONFIG_FILE_PATH is None:
            sources += (TomlConfigSettingsSource(settings_cls, '.idf_ci.toml'),)
        else:
            sources += (TomlConfigSettingsSource(settings_cls, cls.CONFIG_FILE_PATH),)

        return sources

    @property
    def all_component_mapping_regexes(self) -> t.Set[re.Pattern]:
        return {re.compile(regex) for regex in self.component_mapping_regexes + self.extend_component_mapping_regexes}

    def get_modified_components(self, modified_files: t.Iterable[str]) -> t.Set[str]:
        modified_components = set()
        for modified_file in modified_files:
            p = Path(modified_file)
            if p.suffix in self.component_ignored_file_extensions + self.extend_component_ignored_file_extensions:
                continue

            # always use absolute path as posix string
            # Path.resolve return relative path when file does not exist. so use os.path.abspath
            modified_file = Path(os.path.abspath(modified_file)).as_posix()

            for regex in self.all_component_mapping_regexes:
                match = regex.search(modified_file)
                if match:
                    modified_components.add(match.group(1))
                    break

        return modified_components

    def get_apps_list(self) -> t.Optional[t.List[App]]:
        found_files = [p for p in Path('.').glob('app_info_*.txt')]
        if not found_files:
            logger.debug('No built app list files found')
            return None

        logger.debug('Found built app list files: %s', [str(p) for p in found_files])

        apps: t.List[App] = []
        for filepattern in self.built_app_list_filepatterns:
            for filepath in Path('.').glob(filepattern):
                with open(filepath) as fr:
                    for line in fr:
                        line = line.strip()
                        if line:
                            app = json_to_app(line)
                            if app.build_status == BuildStatus.SUCCESS:
                                apps.append(app)
                                logger.debug('App found: %s', apps[-1].build_path)

        if not apps:
            logger.warning(f'No apps found in the built app list files: {found_files}')

        return apps
