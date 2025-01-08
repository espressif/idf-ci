# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import configparser
import os.path
import tempfile
import typing as t
from abc import abstractmethod
from collections import defaultdict
from contextlib import contextmanager

from tomlkit import dump, load

from .compat import PathLike


def _merge_dicts(source: t.Dict, target: t.Dict) -> t.Dict:
    """Recursively merge two dictionaries."""
    for key, value in target.items():
        if key in source and isinstance(source[key], dict) and isinstance(value, dict):
            _merge_dicts(source[key], value)
        else:
            source[key] = value
    return source


class ProfileManager:
    def __init__(self, profiles: t.List[PathLike], default_profile_path: PathLike):
        self.profiles = profiles
        self.default_profile_path = default_profile_path

        self._merged_profile_path: str = None  # type: ignore

    @property
    def merged_profile_path(self) -> str:
        if not self._merged_profile_path:
            self.merge()
        return self._merged_profile_path

    def _resolve_profile_path(self, profile: PathLike) -> PathLike:
        """Resolve 'default' to actual path."""
        return self.default_profile_path if profile == 'default' else profile

    @abstractmethod
    def read(self, profile: PathLike) -> t.Dict:
        """Read a profile file and return the profile as a dictionary."""

    @abstractmethod
    def merge(self) -> None:
        """Merge profiles and write to temporary file and set it as self.merged_profile_path."""

    @contextmanager
    def _merged_profile_writer(self) -> t.Generator[t.IO[str], None, None]:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as fw:
            yield fw

            self._merged_profile_path = fw.name


class IniProfileManager(ProfileManager):
    def read(self, profile: PathLike) -> t.Dict:
        config = configparser.ConfigParser()

        config.read(profile)

        return {s: dict(config.items(s)) for s in config.sections()}

    def merge(self) -> None:
        merged_dict: t.Dict[str, t.Dict] = defaultdict(dict)

        for profile in self.profiles:
            profile = self._resolve_profile_path(profile)

            # ini file must have a section, so we can directly update the merged_dict
            for section, options in self.read(profile).items():
                merged_dict[section].update(options)

        with self._merged_profile_writer() as fw:
            config = configparser.ConfigParser()
            for section, options in merged_dict.items():
                config[section] = options
            config.write(fw)


class TomlProfileManager(ProfileManager):
    def read(self, profile: PathLike) -> t.Dict:
        if not os.path.isfile(profile):
            return {}

        with open(profile) as f:
            return load(f)

    def merge(self) -> None:
        merged_dict: t.Dict = {}

        for profile in self.profiles:
            profile = self._resolve_profile_path(profile)

            # toml dict can be nested, so we need to merge it recursively
            merged_dict = _merge_dicts(merged_dict, self.read(profile))

        with self._merged_profile_writer() as fw:
            dump(merged_dict, fw)
