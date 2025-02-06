# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import logging
import os
import re
import typing as t
from pathlib import Path

from idf_build_apps import App, CMakeApp, json_to_app
from idf_build_apps.constants import BuildStatus
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)

from idf_ci._compat import PathLike

LOGGER = logging.getLogger(__name__)


# noinspection PyDataclass
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

    build_profiles: t.List[PathLike] = ['default']
    test_profiles: t.List[PathLike] = ['default']

    built_app_list_filepatterns: t.List[str] = ['app_info_*.txt']

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
            LOGGER.debug('No built app list files found')
            return None

        LOGGER.debug('Found built app list files: %s', found_files)

        apps: t.List[App] = []
        for filepattern in self.built_app_list_filepatterns:
            for filepath in Path('.').glob(filepattern):
                with open(filepath) as fr:
                    for line in fr:
                        if line := line.strip():
                            apps.append(json_to_app(line, extra_classes=[CMakeApp]))
                            LOGGER.debug('App found: %s', apps[-1].build_path)

        if not apps:
            LOGGER.warning(f'No apps found in the built app list files: {found_files}')

        return [app for app in apps if app.build_status == BuildStatus.SUCCESS]
