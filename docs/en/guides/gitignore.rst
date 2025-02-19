#################################
 Recommended .gitignore Settings
#################################

The ``idf-ci`` tool provides default configurations for CI/CD processes. During execution, it generates various output files like binaries, logs, and build reports. To keep your repository clean and prevent committing generated files, add these entries to your ``.gitignore`` file:

.. code:: text

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
