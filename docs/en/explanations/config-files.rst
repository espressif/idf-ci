##############
 Config Files
##############

Config files store settings. This project uses three types:

- `CI Config File`_: settings for idf-ci_
- `Build Config File`_: settings for idf-build-apps_
- `Test Config File`_: settings for pytest_ and pytest-embedded_

****************
 CI Config File
****************

This file configures idf-ci itself and is typically named ``.idf_ci.toml`` at the repo root. You can create a starter file with ``idf-ci init``.

For more information, see :doc:`../references/ci-config-file`.

*******************
 Build Config File
*******************

This file configures idf-build-apps and is typically named ``.idf_build_apps.toml``. You can create a starter file with ``idf-ci build init``.

For more information, see :doc:`../references/build-config-file`.

******************
 Test Config File
******************

This file configures pytest and pytest-embedded and is typically named ``pytest.ini``. You can create a starter file with ``idf-ci test init``.

For more information, see :doc:`../references/test-config-file`.

.. _idf-build-apps: https://github.com/espressif/idf-build-apps

.. _idf-ci: https://github.com/espressif/idf-ci

.. _pytest: https://github.com/pytest-dev/pytest

.. _pytest-embedded: https://github.com/espressif/pytest-embedded
