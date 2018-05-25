#
# coding=utf-8
"""Shared utility functions"""

import collections
import os
from typing import Optional

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

def namedtuple_with_two_defaults(typename, field_names, default_values=('', '')):
    """Wrapper around namedtuple which lets you treat the last value as optional.

    :param typename: str - type name for the Named tuple
    :param field_names: List[str] or space-separated string of field names
    :param default_values: (optional) 2-element tuple containing the default values for last 2 parameters in named tuple
                            Defaults to an empty string for both of them
    :return: namedtuple type
    """
    T = collections.namedtuple(typename, field_names)
    # noinspection PyUnresolvedReferences
    T.__new__.__defaults__ = default_values
    return T

def cast(current, new):
    """Tries to force a new value into the same type as the current when trying to set the value for a parameter.

    :param current: current value for the parameter, type varies
    :param new: str - new value
    :return: new value with same type as current, or the current value if there was an error casting
    """
    typ = type(current)
    if typ == bool:
        try:
            return bool(int(new))
        except (ValueError, TypeError):
            pass
        try:
            new = new.lower()
        except AttributeError:
            pass
        if (new == 'on') or (new[0] in ('y', 't')):
            return True
        if (new == 'off') or (new[0] in ('n', 'f')):
            return False
    else:
        try:
            return typ(new)
        except (ValueError, TypeError):
            pass
    print("Problem setting parameter (now %s) to %s; incorrect type?" % (current, new))
    return current

def which(editor: str) -> Optional[str]:
    """Find the full path of a given editor.

    Return the full path of the given editor, or None if the editor can
    not be found.

    :param editor: filename of the editor to check, ie 'notepad.exe' or 'vi'
    :return: a full path or None
    """
    import subprocess
    try:
        editor_path = subprocess.check_output(['which', editor], stderr=subprocess.STDOUT).strip()
        editor_path = editor_path.decode()
    except subprocess.CalledProcessError:
        editor_path = None
    return editor_path

def is_text_file(file_path):
    """Returns if a file contains only ASCII or UTF-8 encoded text

    :param file_path: path to the file being checked
    :return: True if the file is a text file, False if it is binary.
    """
    import codecs

    expanded_path = os.path.abspath(os.path.expanduser(file_path.strip()))
    valid_text_file = False

    # Check if the file is ASCII
    try:
        with codecs.open(expanded_path, encoding='ascii', errors='strict') as f:
            # Make sure the file has at least one line of text
            # noinspection PyUnusedLocal
            if sum(1 for line in f) > 0:
                valid_text_file = True
    except IOError:  # pragma: no cover
        pass
    except UnicodeDecodeError:
        # The file is not ASCII. Check if it is UTF-8.
        try:
            with codecs.open(expanded_path, encoding='utf-8', errors='strict') as f:
                # Make sure the file has at least one line of text
                # noinspection PyUnusedLocal
                if sum(1 for line in f) > 0:
                    valid_text_file = True
        except IOError:  # pragma: no cover
            pass
        except UnicodeDecodeError:
            # Not UTF-8
            pass

    return valid_text_file
