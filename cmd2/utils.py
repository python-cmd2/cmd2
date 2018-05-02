#
# coding=utf-8
"""Shared utility functions"""

import collections
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


def namedtuple_with_defaults(typename, field_names, default_values=()):
    """
    Convenience function for defining a namedtuple with default values

    From: https://stackoverflow.com/questions/11351032/namedtuple-and-default-values-for-optional-keyword-arguments

    Examples:
        >>> Node = namedtuple_with_defaults('Node', 'val left right')
        >>> Node()
        Node(val=None, left=None, right=None)
        >>> Node = namedtuple_with_defaults('Node', 'val left right', [1, 2, 3])
        >>> Node()
        Node(val=1, left=2, right=3)
        >>> Node = namedtuple_with_defaults('Node', 'val left right', {'right':7})
        >>> Node()
        Node(val=None, left=None, right=7)
        >>> Node(4)
        Node(val=4, left=None, right=7)
    """
    T = collections.namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, collections.Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T

