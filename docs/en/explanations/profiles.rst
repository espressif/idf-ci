##########
 Profiles
##########

Profiles are a way to store a set of settings. We have three types of profiles:

-  `CI Profile`_: settings for idf-ci_
-  `Build Profile`_: settings for idf-build-apps_
-  `Test Profile`_: settings for pytest_

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
