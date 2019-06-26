# coding=utf-8
"""Support for ANSI escape codes which are used for things like applying style to text"""
import re
from typing import Any

import colorama
from colorama import Fore, Back, Style
from wcwidth import wcswidth

# Regular expression to match ANSI escape codes
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
    'gray': Fore.LIGHTBLACK_EX,
    'lightred': Fore.LIGHTRED_EX,
    'lightblue': Fore.LIGHTBLUE_EX,
    'lightgreen': Fore.LIGHTGREEN_EX,
    'lightyellow': Fore.LIGHTYELLOW_EX,
    'lightmagenta': Fore.LIGHTMAGENTA_EX,
    'lightcyan': Fore.LIGHTCYAN_EX,
    'lightwhite': Fore.LIGHTWHITE_EX,
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
    'gray': Back.LIGHTBLACK_EX,
    'lightred': Back.LIGHTRED_EX,
    'lightblue': Back.LIGHTBLUE_EX,
    'lightgreen': Back.LIGHTGREEN_EX,
    'lightyellow': Back.LIGHTYELLOW_EX,
    'lightmagenta': Back.LIGHTMAGENTA_EX,
    'lightcyan': Back.LIGHTCYAN_EX,
    'lightwhite': Back.LIGHTWHITE_EX,
    'reset': Back.RESET,
}


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from a string.

    :param text: string which may contain ANSI escape codes
    :return: the same string with any ANSI escape codes removed
    """
    return ANSI_ESCAPE_RE.sub('', text)


def ansi_safe_wcswidth(text: str) -> int:
    """
    Wraps wcswidth to make it compatible with colored strings

    :param text: the string being measured
    """
    # Strip ANSI escape codes since they cause wcswidth to return -1
    return wcswidth(strip_ansi(text))


def style(text: Any, *, fg: str = '', bg: str = '', bold: bool = False, underline: bool = False) -> str:
    """
    Applies styles to text

    :param text: Any object compatible with str.format()
    :param fg: foreground color. Accepts color names like 'red' or 'blue'
    :param bg: background color. Accepts color names like 'red' or 'blue'
    :param bold: apply the bold style if True. Defaults to False.
    :param underline: apply the underline style if True. Defaults to False.
    """
    values = []
    text = "{}".format(text)

    # Add styles
    if fg:
        try:
            values.append(FG_COLORS[fg.lower()])
        except KeyError:
            raise ValueError('Color {} does not exist.'.format(fg))
    if bg:
        try:
            values.append(BG_COLORS[bg.lower()])
        except KeyError:
            raise ValueError('Color {} does not exist.'.format(bg))
    if bold:
        values.append(Style.BRIGHT)
    if underline:
        underline_enable = colorama.ansi.code_to_chars(4)
        values.append(underline_enable)

    values.append(text)

    # Remove styles
    if fg:
        values.append(FG_COLORS['reset'])
    if bg:
        values.append(BG_COLORS['reset'])
    if bold:
        values.append(Style.NORMAL)
    if underline:
        underline_disable = colorama.ansi.code_to_chars(24)
        values.append(underline_disable)

    return "".join(values)
