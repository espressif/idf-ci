# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os.path
import re
import typing as t
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


# noinspection PyDataclass
class CiSettings(BaseSettings):
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

    build_profile: str = 'default'  # or your custom profile path

    model_config = SettingsConfigDict(
        toml_file='.idf_ci.toml',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> t.Tuple[PydanticBaseSettingsSource, ...]:
        return TomlConfigSettingsSource(settings_cls), init_settings

    @property
    def all_component_mapping_regexes(self) -> t.Set[re.Pattern]:
        return {re.compile(regex) for regex in self.component_mapping_regexes + self.extend_component_mapping_regexes}

    def get_modified_components(self, modified_files: t.Iterable[str]) -> t.Set[str]:
        modified_components = set()
        for modified_file in modified_files:
            p = Path(modified_file)
            if p.suffix in self.component_ignored_file_extensions + self.extend_component_ignored_file_extensions:
                continue

            # always use posix str
            modified_file = Path(modified_file).as_posix()

            for regex in self.all_component_mapping_regexes:
                match = regex.search(os.path.abspath(modified_file))
                if match:
                    modified_components.add(match.group(1))
                    break

        return modified_components
