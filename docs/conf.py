#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cmd2 documentation build configuration file, created by
sphinx-quickstart on Wed Feb 10 12:05:28 2010.

This file is execfile()d with the current directory set to its
containing dir.

Note that not all possible configuration values are present in this
autogenerated file.

All configuration values have a default; values that are commented out
serve to show the default.

If extensions (or modules to document with autodoc) are in another directory,
add these directories to sys.path here. If the directory is relative to the
documentation root, use os.path.abspath to make it absolute, like shown here.
"""
# Import for custom theme from Read the Docs

import cmd2

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
    'sphinx.ext.todo',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'cmd2'
copyright = '2010-2021, cmd2 contributors'
author = 'cmd2 contributors'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# version will look like x.y.z
version = cmd2.__version__
# release will look like x.y
release = '.'.join(version.split('.')[:2])

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# configure autosectionlabel extension
autosectionlabel_prefix_document = True

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []


# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'cmd2doc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'cmd2.tex', 'cmd2 Documentation', 'Catherine Devlin and Todd Leonhardt', 'manual'),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, 'cmd2', 'cmd2 Documentation', [author], 1)]


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        'cmd2',
        'cmd2 Documentation',
        author,
        'cmd2',
        'A python package for building powerful command-line interpreter (CLI) programs.',
        'Miscellaneous',
    ),
]


# -- Options for Extensions  -------------------------------------------
# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python 3': ('https://docs.python.org/3/', None),
}

# options for autodoc
autodoc_default_options = {'member-order': 'bysource'}

# Ignore nitpicky warnings from autodoc which are occurring for very new versions of Sphinx and autodoc
# They seem to be happening because autodoc is now trying to add hyperlinks to docs for typehint classes
nitpick_ignore = [
    ('py:class', 'cmd2.decorators.CommandParent'),
    ('py:obj', 'cmd2.decorators.CommandParent'),
    ('py:class', 'argparse._SubParsersAction'),
    ('py:class', 'cmd2.utils._T'),
    ('py:class', 'types.FrameType'),
]
