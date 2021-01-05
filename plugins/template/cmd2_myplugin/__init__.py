#
# coding=utf-8
"""Description of myplugin

An overview of what myplugin does.
"""

from .myplugin import (  # noqa: F401
    MyPluginMixin,
    empty_decorator,
)

try:
    # For python 3.8 and later
    import importlib.metadata as importlib_metadata
except ImportError:  # pragma: no cover
    # For everyone else
    import importlib_metadata
try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:  # pragma: no cover
    # package is not installed
    __version__ = 'unknown'
