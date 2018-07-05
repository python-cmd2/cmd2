#
# -*- coding: utf-8 -*-
"""This simply imports certain things for backwards compatibility."""
from .cmd2 import __version__, Cmd, Statement, EmptyStatement, categorize
from .cmd2 import with_argument_list, with_argparser, with_argparser_and_unknown_args, with_category
from .pyscript_bridge import CommandResult