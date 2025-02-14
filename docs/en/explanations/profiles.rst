##########
 Profiles
##########

Profiles are a way to store a set of settings. We have three types of profiles:

-  `CI Profile`_: settings for idf-ci_
-  `Build Profile`_: settings for idf-build-apps_
-  `Test Profile`_: settings for pytest_

Relationship between profiles

.. mermaid::

   graph LR
       C[CI Profile] -- selects --> A[Build Profiles] -- merge --> A_O[Merged Build Profile] --> idf-build-apps
       C -- selects --> B[Test Profiles] -- merge --> B_O[Merged Test Profile] --> pytest

*********************
 How the Merge Works
*********************

Profiles merge according to their type and specified order. The merge process is as follows:

-  **CI Profile**: Merged using TOML format, with later profiles overriding earlier ones.
-  **Build Profile**: Merged using TOML format, with later profiles overriding earlier ones.
-  **Test Profile**: Merged using INI format, with later profiles overriding earlier ones at the key level within each section.

.. warning::

   The merge will only happen to dictionary keys, not to list items. List items will not be appended, but will be replaced with the values from the later profile.

TOML Profile Merging
====================

TOML profiles (used for CI and build profiles) are merged recursively with later profiles overriding earlier ones. The merge preserves nested structures while updating values.

Example:

.. code:: toml

   # profile1.toml
   [section1]
   key1 = "value1"

   [section1.key3]
   k3 = "v3"
   k5 = "v5"

   # profile2.toml
   non_section_key = "non_section_value"
   [section1]
   key2 = "value2"

   [section1.key3]
   k4 = "v4"
   k5 = "v55"

When merging ``profile1.toml`` followed by ``profile2.toml``, the result will be:

.. code:: toml

   non_section_key = "non_section_value"
   [section1]
   key1 = "value1"
   key2 = "value2"

   [section1.key3]
   k3 = "v3"
   k4 = "v4"
   k5 = "v55"  # v55 from profile2 overrides v5 from profile1

INI Profile Merging
===================

INI profiles (used for test profiles) are merged by sections, with later profiles overriding earlier ones at the key level within each section.

Example:

.. code:: ini

   # profile1.ini
   [section1]
   key1=value1

   # profile2.ini
   [section1]
   key2=value2

When merging ``profile1.ini`` followed by ``profile2.ini``, the result will be:

.. code:: ini

   [section1]
   key1=value1
   key2=value2

************
 CI Profile
************

By default it is located at ``.idf_ci.toml`` in the root of the project. It can be overriden by calling ``idf-ci`` with ``--ci-profile`` option.

For more information, please refer to :doc:`../references/ci-profile`.

***************
 Build Profile
***************

Support passing multiple profiles. The order of profiles is important, the later profile will override the former profile. Each profile can be a path to a file or a keyword 'default' which applies the default settings.

For more information, please refer to :doc:`../references/build-profile`.

**************
 Test Profile
**************

Support passing multiple profiles. The order of profiles is important, the later profile will override the former profile. Each profile can be a path to a file or a keyword 'default' which applies the default settings.

For more information, please refer to :doc:`../references/test-profile`.

.. _idf-build-apps: https://github.com/espressif/idf-build-apps

.. _idf-ci: https://github.com/espressif/idf-ci

.. _pytest: https://github.com/pytest-dev/pytest
