#
# coding=utf-8
"""Shared utility functions"""

from . import constants


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from a string.

    :param text: string which may contain ANSI escape codes
    :return: the same string with any ANSI escape codes removed
    """
    return constants.ANSI_ESCAPE_RE.sub('', text)


def strip_quotes(arg: str) -> str:
    """ Strip outer quotes from a string.

     Applies to both single and double quotes.

    :param arg:  string to strip outer quotes from
    :return: same string with potentially outer quotes stripped
    """
    if len(arg) > 1 and arg[0] == arg[-1] and arg[0] in constants.QUOTES:
        arg = arg[1:-1]
    return arg
