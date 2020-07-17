#
# coding=utf-8
"""cmd2 Modular Command Mixin

Allows registration of arbitrary functions and CommandSets as commands in a cmd2 application
"""

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

from .command_definition import CommandSet, with_default_category, register_command
from .modular_mixin import ModularCommandsMixin

__all__ = [
    'CommandSet',
    'ModularCommandsMixin',
    'register_command',
    'with_default_category',
]
