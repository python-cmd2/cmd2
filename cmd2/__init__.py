#
# -*- coding: utf-8 -*-
# flake8: noqa F401
"""This simply imports certain things for backwards compatibility."""

import importlib.metadata as importlib_metadata

try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:  # pragma: no cover
    # package is not installed
    pass

from . import plugin
from .ansi import (
    Bg,
    Cursor,
    EightBitBg,
    EightBitFg,
    Fg,
    RgbBg,
    RgbFg,
    TextStyle,
    style,
)
from .argparse_completer import set_default_ap_completer_type
from .argparse_custom import (
    Cmd2ArgumentParser,
    Cmd2AttributeWrapper,
    CompletionItem,
    register_argparse_argument_parameter,
    set_default_argument_parser_type,
)
from .cmd2 import Cmd
from .command_definition import (
    CommandSet,
    with_default_category,
)
from .constants import (
    COMMAND_NAME,
    DEFAULT_SHORTCUTS,
)
from .decorators import (
    as_subcommand_to,
    with_argparser,
    with_argument_list,
    with_category,
)
from .exceptions import (
    Cmd2ArgparseError,
    CommandSetRegistrationError,
    CompletionError,
    PassThroughException,
    SkipPostcommandHooks,
)
from .parsing import Statement
from .py_bridge import CommandResult
from .utils import (
    CompletionMode,
    CustomCompletionSettings,
    Settable,
    categorize,
)

__all__: list[str] = [
    'COMMAND_NAME',
    'DEFAULT_SHORTCUTS',
    # ANSI Exports
    'Cursor',
    'Bg',
    'Fg',
    'EightBitBg',
    'EightBitFg',
    'RgbBg',
    'RgbFg',
    'TextStyle',
    'style',
    # Argparse Exports
    'Cmd2ArgumentParser',
    'Cmd2AttributeWrapper',
    'CompletionItem',
    'register_argparse_argument_parameter',
    'set_default_ap_completer_type',
    'set_default_argument_parser_type',
    # Cmd2
    'Cmd',
    'CommandResult',
    'CommandSet',
    'Statement',
    # Decorators
    'with_argument_list',
    'with_argparser',
    'with_category',
    'with_default_category',
    'as_subcommand_to',
    # Exceptions
    'Cmd2ArgparseError',
    'CommandSetRegistrationError',
    'CompletionError',
    'PassThroughException',
    'SkipPostcommandHooks',
    # modules
    'plugin',
    # Utilities
    'categorize',
    'CompletionMode',
    'CustomCompletionSettings',
    'Settable',
]
