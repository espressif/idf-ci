# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import textwrap

from idf_ci.profiles import IniProfileManager, TomlProfileManager


class TestIniProfile:
    def test_read_valid_profile(self, tmp_path):
        profile_path = tmp_path / 'valid_profile.ini'
        profile_path.write_text(
            textwrap.dedent("""
            [section]
            key=value
        """)
        )

        manager = IniProfileManager([profile_path], profile_path)
        profile = manager.read(profile_path)
        assert profile['section']['key'] == 'value'

    def test_read_nonexistent_profile(self, tmp_path):
        profile_path = tmp_path / 'nonexistent_profile.ini'
        manager = IniProfileManager([profile_path], profile_path)
        profile = manager.read(profile_path)
        assert profile == {}

    def test_merge_multiple_profiles(self, tmp_path):
        profile1_path = tmp_path / 'profile1.ini'
        profile2_path = tmp_path / 'profile2.ini'
        profile1_path.write_text(
            textwrap.dedent("""
            [section1]
            key1=value1
        """)
        )
        profile2_path.write_text(
            textwrap.dedent("""
            [section1]
            key2=value2
        """)
        )

        manager = IniProfileManager([profile1_path, profile2_path], profile1_path)
        merged_profile = manager.read(manager.merged_profile_path)
        assert merged_profile['section1']['key1'] == 'value1'
        assert merged_profile['section1']['key2'] == 'value2'

    def test_merge_with_default_profile(self, tmp_path):
        default_profile_path = tmp_path / 'default_profile.ini'
        profile_path = tmp_path / 'profile.ini'
        default_profile_path.write_text(
            textwrap.dedent("""
            [default_section]
            default_key=default_value
        """)
        )
        profile_path.write_text(
            textwrap.dedent("""
            [section]
            key=value
        """)
        )

        manager = IniProfileManager(['default', profile_path], default_profile_path)
        merged_profile = manager.read(manager.merged_profile_path)
        assert merged_profile['default_section']['default_key'] == 'default_value'
        assert merged_profile['section']['key'] == 'value'


class TestTomlProfile:
    def test_read_valid_profile(self, tmp_path):
        profile_path = tmp_path / 'valid_profile.toml'
        profile_path.write_text(
            textwrap.dedent("""
            [section]
            key = 'value'
        """)
        )

        manager = TomlProfileManager([profile_path], profile_path)
        profile = manager.read(profile_path)
        assert profile['section']['key'] == 'value'

    def test_read_nonexistent_profile(self, tmp_path):
        profile_path = tmp_path / 'nonexistent_profile.toml'
        manager = TomlProfileManager([profile_path], profile_path)
        profile = manager.read(profile_path)
        assert profile == {}

    def test_merge_multiple_profiles(self, tmp_path):
        profile1_path = tmp_path / 'profile1.toml'
        profile2_path = tmp_path / 'profile2.toml'
        profile1_path.write_text(
            textwrap.dedent("""
            [section1]
            key1 = 'value1'

            [section1.key3]
            k3 = 'v3'
            k5 = 'v5'
        """)
        )
        profile2_path.write_text(
            textwrap.dedent("""
            non_section_key = 'non_section_value'
            [section1]
            key2 = 'value2'

            [section1.key3]
            k4 = 'v4'
            k5 = 'v55'
        """)
        )

        manager = TomlProfileManager([profile1_path, profile2_path], profile1_path)
        merged_profile = manager.read(manager.merged_profile_path)
        assert merged_profile['section1']['key1'] == 'value1'
        assert merged_profile['section1']['key2'] == 'value2'
        assert merged_profile['section1']['key3'] == {
            'k3': 'v3',
            'k4': 'v4',
            'k5': 'v55',
        }
        assert merged_profile['non_section_key'] == 'non_section_value'

    def test_merge_with_default_profile(self, tmp_path):
        default_profile_path = tmp_path / 'default_profile.toml'
        profile_path = tmp_path / 'profile.toml'
        default_profile_path.write_text(
            textwrap.dedent("""
            [default_section]
            default_key = 'default_value'
        """)
        )
        profile_path.write_text(
            textwrap.dedent("""
            [section]
            key = 'value'
        """)
        )

        manager = TomlProfileManager(['default', profile_path], default_profile_path)
        merged_profile = manager.read(manager.merged_profile_path)
        assert merged_profile['default_section']['default_key'] == 'default_value'
        assert merged_profile['section']['key'] == 'value'
