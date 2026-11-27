# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import sys
from importlib.metadata import version as package_version
from pathlib import Path

# Make the local extensions in `_ext` importable.
sys.path.insert(0, str(Path(__file__).parent / "_ext"))

# -- Project information -----------------------------------------------------

project = "deltakit-compile"
version = package_version("deltakit-compile")
copyright = "2020-2026, Riverlane"  # noqa: A001
author = "Riverlane Ltd and contributors"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "myst_nb",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx_design",
    # Builds the API reference: see `_ext/deltakit_api.py`.
    "deltakit_api",
    # Builds the sidebar shared by the Deltakit documentation sites: see `_ext/deltakit_nav.py`.
    "deltakit_nav",
]
templates_path = ["_templates"]
myst_enable_extensions = [
    "colon_fence",
    "dollarmath",
    "amsmath",
    "substitution",
]
# Generate GitHub-style anchors for headings, so `[text](#some-heading)` links
# resolve both on GitHub and in the built docs.
myst_heading_anchors = 3

# Run every notebook page on each build, so the docs fail when an example no
# longer works with the current code.
nb_execution_mode = "force"
nb_execution_timeout = 300

autosectionlabel_prefix_document = True
autosummary_generate = True
autosummary_generate_overwrite = True  # Sphinx ≥ 7.2

# include class docstring + __init__ docstring (shows Parameters)
autoclass_content = "both"
numpydoc_show_class_members = False
autodoc_member_order = "bysource"

# Docstrings write code in single backticks, as in Markdown. Treat that as a cross-reference,
# which falls back to code formatting when nothing matches, rather than as emphasis.
default_role = "py:obj"

# Link types and base classes from other projects to their own documentation.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "xdsl": ("https://docs.xdsl.dev/", None),
}

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "Thumbs.db",
    ".DS_Store",
    "_build",
    # Copies of the main Deltakit site's contributing guide and policies. GitHub shows them on
    # this repository's pages, but the site links to the main site's guide instead.
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "RELEASE.md",
    "SECURITY.md",
]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# Title for name link at the top of the documentation home page.
html_title = f"{project} v{version}"

# Favicon setup:
# https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_favicon
html_favicon = "logo/deltakit_favicon.png"

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_permalinks_icon = "<span>#</span>"
html_theme = "sphinxawesome_theme"

# Show the sidebar shared by the Deltakit documentation sites in place of the theme's table of
# contents. This site owns the `deltakit-compile` entry, which expands into its own pages.
html_sidebars = {"**": ["sidebar_main_nav_links.html", "sidebar_deltakit_nav.html"]}
deltakit_nav_current = "deltakit-compile"

# Paths that contain custom static files (such as style sheets), relative to this
# directory. They are copied after the theme's static files.
html_static_path = ["_static"]

# Custom style sheets, relative to the paths in `html_static_path`.
html_css_files = ["css/custom.css"]

# no link to an *.rst source
html_show_sourcelink = False

# Theme options are theme-specific and customise the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation at https://www.sphinx-doc.org/en/master/usage/theming.html.
html_theme_options = {
    "logo_light": "logo/deltakit_favicon.png",
    "logo_dark": "logo/deltakit_favicon.png",
}

# Configure MathJax v3
mathjax3_config = {
    "tex": {
        "packages": {"[+]": ["physics"]}  # Add the physics package
    },
    "loader": {
        "load": ["[tex]/physics"]  # Load physics extension
    },
}

# Highlight unlabelled blocks as Python, falling back to plain text without a warning: docstrings
# also use literal blocks for IR syntax and assembly format grammars, which are not Python.
highlight_language = "default"

suppress_warnings = [
    "autosummary.import_cycle",
]

linkcheck_timeout = 360
linkcheck_retries = 2

# `npmjs.com` sits behind bot protection that answers non-browser clients with
# HTTP 403, so `linkcheck` reports these URLs as broken from CI runners even
# though they resolve fine in a browser.
linkcheck_ignore = [
    r"https://www\.npmjs\.com/.*",
    # Hosts that answer a normal request but stall or refuse for the CI runners.
    # Raising linkcheck_timeout does not help there. It only makes the job wait
    # longer before failing on something that says nothing about the documentation.
    # Both were checked by hand on 2026-08-04 and answered 200 in under a second.
    #
    # Read timed out at the full linkcheck_timeout in runs 30798353783 and
    # 30752780915. Unreachable in 30797197824.
    r"https://learn\.scientific-python\.org/",
    # Answers 403 to requests that do not look like a browser, seen in run
    # 30797197824.
    r"https://www\.twilio\.com/",
]
