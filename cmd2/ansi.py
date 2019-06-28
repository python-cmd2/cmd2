# coding=utf-8
"""Support for ANSI escape sequences which are used for things like applying style to text"""
import functools
import re
from typing import Any, IO

import colorama
from colorama import Fore, Back, Style
from wcwidth import wcswidth

# Values for allow_ansi setting
ANSI_NEVER = 'Never'
ANSI_TERMINAL = 'Terminal'
ANSI_ALWAYS = 'Always'

# Controls when ANSI escape sequences are allowed in output
allow_ansi = ANSI_TERMINAL

# Regular expression to match ANSI escape sequences
ANSI_ESCAPE_RE = re.compile(r'\x1b[^m]*m')

# Foreground color presets
FG_COLORS = {
    'black': Fore.BLACK,
    'red': Fore.RED,
    'green': Fore.GREEN,
    'yellow': Fore.YELLOW,
    'blue': Fore.BLUE,
    'magenta': Fore.MAGENTA,
    'cyan': Fore.CYAN,
    'white': Fore.WHITE,
    'bright_black': Fore.LIGHTBLACK_EX,
    'bright_red': Fore.LIGHTRED_EX,
    'bright_green': Fore.LIGHTGREEN_EX,
    'bright_yellow': Fore.LIGHTYELLOW_EX,
    'bright_blue': Fore.LIGHTBLUE_EX,
    'bright_magenta': Fore.LIGHTMAGENTA_EX,
    'bright_cyan': Fore.LIGHTCYAN_EX,
    'bright_white': Fore.LIGHTWHITE_EX,
    'reset': Fore.RESET,
}

# Background color presets
BG_COLORS = {
    'black': Back.BLACK,
    'red': Back.RED,
    'green': Back.GREEN,
    'yellow': Back.YELLOW,
    'blue': Back.BLUE,
    'magenta': Back.MAGENTA,
    'cyan': Back.CYAN,
    'white': Back.WHITE,
    'bright_black': Back.LIGHTBLACK_EX,
    'bright_red': Back.LIGHTRED_EX,
    'bright_green': Back.LIGHTGREEN_EX,
    'bright_yellow': Back.LIGHTYELLOW_EX,
    'bright_blue': Back.LIGHTBLUE_EX,
    'bright_magenta': Back.LIGHTMAGENTA_EX,
    'bright_cyan': Back.LIGHTCYAN_EX,
    'bright_white': Back.LIGHTWHITE_EX,
    'reset': Back.RESET,
}

FG_RESET = FG_COLORS['reset']
BG_RESET = BG_COLORS['reset']
RESET_ALL = Style.RESET_ALL

# ANSI escape sequences not provided by colorama
UNDERLINE_ENABLE = colorama.ansi.code_to_chars(4)
UNDERLINE_DISABLE = colorama.ansi.code_to_chars(24)


def strip_ansi(text: str) -> str:
    """
    Strip ANSI escape sequences from a string.

    :param text: string which may contain ANSI escape sequences
    :return: the same string with any ANSI escape sequences removed
    """
    return ANSI_ESCAPE_RE.sub('', text)


def ansi_safe_wcswidth(text: str) -> int:
    """
    Wrap wcswidth to make it compatible with strings that contains ANSI escape sequences

    :param text: the string being measured
    """
    # Strip ANSI escape sequences since they cause wcswidth to return -1
    return wcswidth(strip_ansi(text))


def ansi_aware_write(fileobj: IO, msg: str) -> None:
    """
    Write a string to a fileobject and strip its ANSI escape sequences if required by allow_ansi setting

    :param fileobj: the file object being written to
    :param msg: the string being written
    """
    if allow_ansi.lower() == ANSI_NEVER.lower() or \
            (allow_ansi.lower() == ANSI_TERMINAL.lower() and not fileobj.isatty()):
        msg = strip_ansi(msg)
    fileobj.write(msg)


def fg_lookup(fg_name: str) -> str:
    """Look up ANSI escape codes based on foreground color name.

    :param fg_name: foreground color name to look up ANSI escape code(s) for
    :return: ANSI escape code(s) associated with this color
    :raises ValueError if the color cannot be found
    """
    try:
        ansi_escape = FG_COLORS[fg_name.lower()]
    except KeyError:
        raise ValueError('Foreground color {!r} does not exist.'.format(fg_name))
    return ansi_escape


def bg_lookup(bg_name: str) -> str:
    """Look up ANSI escape codes based on background color name.

    :param bg_name: background color name to look up ANSI escape code(s) for
    :return: ANSI escape code(s) associated with this color
    :raises ValueError if the color cannot be found
    """
    try:
        ansi_escape = BG_COLORS[bg_name.lower()]
    except KeyError:
        raise ValueError('Background color {!r} does not exist.'.format(bg_name))
    return ansi_escape


def style(text: Any, *, fg: str = '', bg: str = '', bold: bool = False, underline: bool = False) -> str:
    """Styles a string with ANSI colors and/or styles and returns the new string.

    The styling is self contained which means that at the end of the string reset code(s) are issued
    to undo whatever styling was done at the beginning.

    :param text: Any object compatible with str.format()
    :param fg: foreground color. Relies on `fg_lookup()` to retrieve ANSI escape based on name. Defaults to no color.
    :param bg: background color. Relies on `bg_lookup()` to retrieve ANSI escape based on name. Defaults to no color.
    :param bold: apply the bold style if True. Defaults to False.
    :param underline: apply the underline style if True. Defaults to False.
    :return: the stylized string
    """
    # List of strings that add style
    additions = []

    # List of strings that remove style
    removals = []

    # Convert the text object into a string if it isn't already one
    text = "{}".format(text)

    # Process the style settings
    if fg:
        additions.append(fg_lookup(fg))
        removals.append(FG_RESET)

    if bg:
        additions.append(bg_lookup(bg))
        removals.append(BG_RESET)

    if bold:
        additions.append(Style.BRIGHT)
        removals.append(Style.NORMAL)

    if underline:
        additions.append(UNDERLINE_ENABLE)
        removals.append(UNDERLINE_DISABLE)

    # Combine the ANSI escape sequences with the text
    return "".join(additions) + text + "".join(removals)


# Default styles for printing strings of various types.
# These can be altered to suit an application's needs and only need to be a
# function with the following structure: func(str) -> str
style_success = functools.partial(style, fg='green', bold=True)
style_warning = functools.partial(style, fg='bright_yellow')
style_error = functools.partial(style, fg='bright_red')
