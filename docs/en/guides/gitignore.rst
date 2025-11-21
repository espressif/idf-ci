Recommended .gitignore Settings
===============================

The ``idf-ci`` tool provides default configurations for CI/CD processes. During execution, it generates various output files like binaries, logs, and build reports. To keep your repository clean and prevent committing generated files, add these entries to your ``.gitignore`` file:

.. code-block:: text

    # MacOS directory files
    .DS_Store

    # cache dir
    .cache/

    .pytest_cache/
    __pycache__/

    # esp-idf built binaries
    build/
    build_*_*/
    sdkconfig

    # idf-ci build run output
    build_summary_*.xml
    app_info_*.txt
    size_info_*.txt

    # pytest-embedded log folder
    pytest_embedded_log/

    # idf-component-manager output
    dependencies.lock

    # idf-component-manager
    managed_components/

If you need more specific configurations, refer to `esp-idf's .gitignore on GitHub <https://github.com/espressif/esp-idf/blob/master/.gitignore>`_ for additional recommendations.
