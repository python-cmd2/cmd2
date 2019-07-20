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

from .ansi import style
from .argparse_custom import Cmd2ArgumentParser, CompletionItem
from .cmd2 import Cmd, Statement, EmptyStatement, categorize
from .cmd2 import with_argument_list, with_argparser, with_argparser_and_unknown_args, with_category
from .constants import DEFAULT_SHORTCUTS
from .py_bridge import CommandResult
