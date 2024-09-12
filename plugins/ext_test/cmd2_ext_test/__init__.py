#
# coding=utf-8
"""cmd2 External Python Testing Mixin

Allows developers to exercise their cmd2 application using the PyScript interface
"""

import importlib.metadata as importlib_metadata

try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:  # pragma: no cover
    # package is not installed
    __version__ = 'unknown'

from .cmd2_ext_test import (
    ExternalTestMixin,
)

__all__ = ['ExternalTestMixin']
