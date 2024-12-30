# SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0
import os.path
import re
import sys
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    PydanticBaseSettingsSource,
)

import typing as t


class CiSettings(BaseSettings):
    component_mapping_regexes: t.List[str] = [  # noqa
        '/components/(.+)/',
        '/common_components/(.+)/',
    ]
    extend_component_mapping_regexes: t.List[str] = []  # noqa

    model_config = SettingsConfigDict(
        toml_file='.idf_ci.toml',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: t.Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> t.Tuple[PydanticBaseSettingsSource, ...]:
        return TomlConfigSettingsSource(settings_cls), init_settings

    @property
    def all_component_mapping_regexes(self) -> t.Set[re.Pattern]:
        return {re.compile(regex) for regex in self.component_mapping_regexes + self.extend_component_mapping_regexes}

    def get_modified_components(self, modified_files: t.Iterable[str]) -> t.Set[str]:
        modified_components = set()
        for modified_file in modified_files:
            # always use posix str
            if sys.platform == 'win32':
                modified_file = Path(modified_file).as_posix()

            for regex in self.all_component_mapping_regexes:
                match = regex.search(os.path.abspath(modified_file))
                if match:
                    modified_components.add(match.group(1))
                    break

        return modified_components
