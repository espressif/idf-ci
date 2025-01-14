# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import re
import typing as t
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)


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

    build_profiles: t.List[str] = ['default']
    test_profiles: t.List[str] = ['default']

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
