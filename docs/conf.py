# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------

project = "etho"
copyright = "2026, Jan Clemens"
author = "Jan Clemens"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx_tabs.tabs",
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_nb",
    "sphinx.ext.autosummary",
    "sphinx_panels",
    "sphinxcontrib.images",
    "sphinx.ext.autosectionlabel",
    "sphinx_copybutton",
    "sphinx_iconify",
    "sphinx_design",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The master toctree document.
master_doc = "index"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
exclude_patterns += ["README.md"]

html_static_path = ["_static"]

html_theme_options = {
    "accent_color": "violet",
    "light_logo": "_static/etho_light.svg",
    "dark_logo": "_static/etho_dark.svg",
    "github_url": "https://github.com/janclemenslab/etho",
    "nav_links": [
        {"title": "Installation", "url": "install"},
        {"title": "Tutorial", "url": "tutorial"},
        {"title": "Configuration", "url": "configuration/configuration"},
    ],
}


# Autosummary linkcode resolution
# https://www.sphinx-doc.org/en/master/usage/extensions/linkcode.html
def linkcode_resolve(domain, info):
    """Resolve GitHub URLs for linkcode extension."""

    if domain != "py":
        return None

    if not info["module"]:
        return None

    try:
        filename = docs.utils.resolve(info["module"], info["fullname"])
        if filename is None:
            return None
        return f"https://github.com/janclemenslab/etho/blob/master/{filename}"
    except:
        print(info)
        raise


autosummary_generate = True
autoclass_content = "both"

# Enable automatic role inference as a Python object for autodoc.
# This automatically converts object references to their appropriate role,
# making it much easier (and more legible) to insert references in docstrings.
#   Ex: `MyClass` -> :class:`MyClass`
# https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-default_role
default_role = "py:obj"
autosectionlabel_prefix_document = True

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = "furo"
html_theme = "shibuya"


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
