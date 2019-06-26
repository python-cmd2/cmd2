# coding=utf-8
"""Support for ANSI escape codes which are used for things like applying style to text"""
import re
from typing import Any, Optional

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


# ANSI escape strings not provided by colorama
UNDERLINE_ENABLE = colorama.ansi.code_to_chars(4)
UNDERLINE_DISABLE = colorama.ansi.code_to_chars(24)


class TextStyle:
    """Style settings for text"""

    def __init__(self, *, fg: str = '', bg: str = '', bold: bool = False, underline: bool = False):
        """
        Initializer
        :param fg: foreground color. Expects color names in FG_COLORS (e.g. 'lightred'). Defaults to blank.
        :param bg: background color. Expects color names in BG_COLORS (e.g. 'black'). Defaults to blank.
        :param bold: apply the bold style if True. Defaults to False.
        :param underline: apply the underline style if True. Defaults to False.
        """
        self.fg = fg
        self.bg = bg
        self.bold = bold
        self.underline = underline


# Default styles. These can be altered to suit an application's needs.
SuccessStyle = TextStyle(fg='green', bold=True)
WarningStyle = TextStyle(fg='lightyellow')
ErrorStyle = TextStyle(fg='lightred')


def style(text: Any, text_style: Optional[TextStyle] = None, *,
          fg: Optional[str] = None, bg: Optional[str] = None,
          bold: Optional[bool] = None, underline: Optional[bool] = None) -> str:
    """
    Applies a style to text

    :param text: Any object compatible with str.format()
    :param text_style: a TextStyle object. Defaults to None.

    The following are keyword-only parameters which allow calling style without creating a TextStyle object
        style(text, fg='blue')

    They can also be used to override a setting in a provided TextStyle
        style(text, ErrorStyle, underline=True)

    :param fg: foreground color. Expects color names in FG_COLORS (e.g. 'lightred'). Defaults to None.
    :param bg: background color. Expects color names in BG_COLORS (e.g. 'black'). Defaults to None.
    :param bold: apply the bold style if True. Defaults to None.
    :param underline: apply the underline style if True. Defaults to None.

    :return: the stylized string
    """
    # List of strings that add style
    additions = []

    # List of strings that remove style
    removals = []

    # Convert the text object into a string if it isn't already one
    text = "{}".format(text)

    # Figure out what parameters to use
    if fg is None and text_style is not None:
        fg = text_style.fg
    if bg is None and text_style is not None:
        bg = text_style.bg
    if bold is None and text_style is not None:
        bold = text_style.bold
    if underline is None and text_style is not None:
        underline = text_style.underline

    # Process the style settings
    if fg:
        try:
            additions.append(FG_COLORS[fg.lower()])
            removals.append(FG_COLORS['reset'])
        except KeyError:
            raise ValueError('Color {} does not exist.'.format(fg))

    if bg:
        try:
            additions.append(BG_COLORS[bg.lower()])
            removals.append(BG_COLORS['reset'])
        except KeyError:
            raise ValueError('Color {} does not exist.'.format(bg))

    if bold:
        additions.append(Style.BRIGHT)
        removals.append(Style.NORMAL)

    if underline:
        additions.append(UNDERLINE_ENABLE)
        removals.append(UNDERLINE_DISABLE)

    # Combine the ANSI escape strings with the text
    return "".join(additions) + text + "".join(removals)
