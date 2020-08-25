#
# -*- coding: utf-8 -*-
# flake8: noqa F401
"""This simply imports certain things for backwards compatibility."""

try:
    # For python 3.8 and later
    import importlib.metadata as importlib_metadata
except ImportError:
    # For everyone else
    import importlib_metadata
try:
    __version__ = importlib_metadata.version(__name__)
except importlib_metadata.PackageNotFoundError:  # pragma: no cover
    # package is not installed
    pass

from .ansi import style, fg, bg
from .argparse_custom import Cmd2ArgumentParser, Cmd2AttributeWrapper, CompletionItem, set_default_argument_parser

# Check if user has defined a module that sets a custom value for argparse_custom.DEFAULT_ARGUMENT_PARSER
import argparse
cmd2_parser_module = getattr(argparse, 'cmd2_parser_module', None)
if cmd2_parser_module is not None:
    import importlib
    importlib.import_module(cmd2_parser_module)

# Get the current value for argparse_custom.DEFAULT_ARGUMENT_PARSER
from .argparse_custom import DEFAULT_ARGUMENT_PARSER
from .cmd2 import Cmd
from .command_definition import CommandSet, with_default_category
from .constants import COMMAND_NAME, DEFAULT_SHORTCUTS
from .decorators import with_argument_list, with_argparser, with_argparser_and_unknown_args, with_category, \
    as_subcommand_to
from .exceptions import Cmd2ArgparseError, SkipPostcommandHooks, CommandSetRegistrationError
from . import plugin
from .parsing import Statement
from .py_bridge import CommandResult
from .utils import categorize, CompletionError, Settable
