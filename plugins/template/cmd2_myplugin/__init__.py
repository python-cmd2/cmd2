#
# coding=utf-8
"""Description of myplugin

An overview of what myplugin does.
"""

import importlib.metadata as importlib_metadata

from .myplugin import (  # noqa: F401
    MyPluginMixin,
    empty_decorator,
)

try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:  # pragma: no cover
    # package is not installed
    __version__ = 'unknown'
