# coding=utf-8
"""
Test the build of the sphinx documentation

Released under MIT license, see LICENSE file
"""
import os

import pytest

from sphinx.application import Sphinx

DOCS_SRCDIR = 'docs'
DOCS_BUILDDIR = os.path.join('docs', '_build')
DOCS_TREEDIR = os.path.join(DOCS_BUILDDIR, 'doctrees')

def test_html_documentation():
    # if you want really strict checking, set warningiserror=True
    docs = Sphinx(DOCS_SRCDIR,
                  DOCS_SRCDIR,
                  DOCS_BUILDDIR,
                  DOCS_TREEDIR,
                  buildername='html',
                  warningiserror=False,
    )
    # this throws exceptions for errors, which pytest then
    # treats as a failure
    docs.build(force_all=True)
