#
# -*- coding: utf-8 -*-
#
from .cmd2 import __version__, Cmd, set_posix_shlex, set_strip_quotes, AddSubmenu, CmdResult, categorize
from .cmd2 import with_argument_list, with_argparser, with_argparser_and_unknown_args, with_category

# Used for tab completion and word breaks. Do not change.
QUOTES = ['"', "'"]
REDIRECTION_CHARS = ['|', '<', '>']


def strip_quotes(arg: str) -> str:
    """ Strip outer quotes from a string.

     Applies to both single and double quotes.

    :param arg:  string to strip outer quotes from
    :return: same string with potentially outer quotes stripped
    """
    if len(arg) > 1 and arg[0] == arg[-1] and arg[0] in QUOTES:
        arg = arg[1:-1]
    return arg
