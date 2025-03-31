# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import subprocess

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'idf-ci'
project_homepage = 'https://github.com/espressif/idf-ci'
copyright = '2025, Espressif Systems (Shanghai) Co., Ltd.'  # noqa: A001
author = 'Fu Hanxi'
languages = ['en']
version = '0.x'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_copybutton',
    'myst_parser',
    'sphinxcontrib.mermaid',
    'sphinxarg.ext',
    'sphinx_tabs.tabs',
    'sphinxcontrib.autodoc_pydantic',
]

templates_path = ['../_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_css_files = ['theme_overrides.css']
html_logo = '../_static/espressif-logo.svg'
html_static_path = ['../_static']
html_theme = 'sphinx_rtd_theme'


def generate_api_docs(language):
    shutil.rmtree(os.path.join(os.path.dirname(__file__), language, 'references', 'api'), ignore_errors=True)

    subprocess.run(
        [
            'sphinx-apidoc',
            '-f',
            '-H',
            'API Reference',
            '--no-headings',
            '-t',
            '_apidoc_templates',
            '-o',
            os.path.join(os.path.dirname(__file__), language, 'references', 'api'),
            os.path.join(os.path.dirname(__file__), '..', 'idf_ci'),
            os.path.join(os.path.dirname(__file__), '..', 'idf_ci', 'settings.py'),
            os.path.join(os.path.dirname(__file__), '..', 'idf_ci', 'idf_gitlab', 'envs.py'),
        ]
    )
