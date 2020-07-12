#
# coding=utf-8
"""Description of myplugin

An overview of what myplugin does.
"""

try:
    # For python 3.8 and later
    import importlib.metadata as importlib_metadata
except ImportError:
    # For everyone else
    import importlib_metadata
try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:
    # package is not installed
    __version__ = 'unknown'

from .cmd2_ext_test import ExternalTestMixin

__all__ = [
    'ExternalTestMixin'
]
