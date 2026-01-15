#################################
 Recommended .gitignore Settings
#################################

The ``idf-ci`` tool generates output such as binaries, logs, and reports. To keep your repository clean and avoid committing generated files, add these entries to your ``.gitignore`` file. Adjust as needed if you want to keep specific artifacts under version control.

.. code-block:: text

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
