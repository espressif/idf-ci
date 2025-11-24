# idf-ci docs

1. Install dependencies

    ```sh
    pip install '.[doc]'
    ```

2. Build

    ```sh
    sphinx-build docs/en docs/html_output
    ```

3. Run for example using python `http_server`

    ```sh
    python -m http.server -d docs/html_output
    ```
