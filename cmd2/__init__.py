#
# -*- coding: utf-8 -*-
# flake8: noqa F401
"""This simply imports certain things for backwards compatibility."""

from pkg_resources import get_distribution, DistributionNotFound
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass

from .ansi import style, fg, bg
from .argparse_custom import Cmd2ArgumentParser, CompletionItem, set_default_argument_parser

# Check if user has defined a module that sets a custom value for argparse_custom.DEFAULT_ARGUMENT_PARSER
import argparse
cmd2_parser_module = getattr(argparse, 'cmd2_parser_module', None)
if cmd2_parser_module is not None:
    import importlib
    importlib.import_module(cmd2_parser_module)

# Get the current value for argparse_custom.DEFAULT_ARGUMENT_PARSER
from .argparse_custom import DEFAULT_ARGUMENT_PARSER
from .cmd2 import Cmd
from .constants import COMMAND_NAME, DEFAULT_SHORTCUTS
from .decorators import with_argument_list, with_argparser, with_argparser_and_unknown_args, with_category
from .parsing import Statement
from .py_bridge import CommandResult
from .utils import categorize, CompletionError, Settable
