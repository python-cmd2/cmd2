# coding=utf-8
"""Support for ANSI escape sequences which are used for things like applying style to text"""
import functools
import re
from typing import Any, IO

import colorama
from colorama import Fore, Back, Style
from wcwidth import wcswidth

# On Windows, filter ANSI escape codes out of text sent to stdout/stderr, and replace them with equivalent Win32 calls
colorama.init(strip=False)

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

BRIGHT = Style.BRIGHT
NORMAL = Style.NORMAL

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


def async_alert_str(*, terminal_columns: int, prompt: str, line: str, cursor_offset: int, alert_msg: str) -> str:
    """Calculate the desired string, including ANSI escape codes, for displaying an asynchronous alert message.

    :param terminal_columns: terminal width (number of columns)
    :param prompt: prompt that is displayed on the current line
    :param line: current contents of the Readline line buffer
    :param cursor_offset: the offset of the current cursor position within line
    :param alert_msg: the message to display to the user
    :return: the correct string so that the alert message appears to the user to be printed above the current line.
    """
    from colorama import Cursor
    # Split the prompt lines since it can contain newline characters.
    prompt_lines = prompt.splitlines()

    # Calculate how many terminal lines are taken up by all prompt lines except for the last one.
    # That will be included in the input lines calculations since that is where the cursor is.
    num_prompt_terminal_lines = 0
    for line in prompt_lines[:-1]:
        line_width = ansi_safe_wcswidth(line)
        num_prompt_terminal_lines += int(line_width / terminal_columns) + 1

    # Now calculate how many terminal lines are take up by the input
    last_prompt_line = prompt_lines[-1]
    last_prompt_line_width = ansi_safe_wcswidth(last_prompt_line)

    input_width = last_prompt_line_width + ansi_safe_wcswidth(line)

    num_input_terminal_lines = int(input_width / terminal_columns) + 1

    # Get the cursor's offset from the beginning of the first input line
    cursor_input_offset = last_prompt_line_width + cursor_offset

    # Calculate what input line the cursor is on
    cursor_input_line = int(cursor_input_offset / terminal_columns) + 1

    # Create a string that when printed will clear all input lines and display the alert
    terminal_str = ''

    # Move the cursor down to the last input line
    if cursor_input_line != num_input_terminal_lines:
        terminal_str += Cursor.DOWN(num_input_terminal_lines - cursor_input_line)

    # Clear each line from the bottom up so that the cursor ends up on the first prompt line
    total_lines = num_prompt_terminal_lines + num_input_terminal_lines
    terminal_str += (colorama.ansi.clear_line() + Cursor.UP(1)) * (total_lines - 1)

    # Clear the first prompt line
    terminal_str += colorama.ansi.clear_line()

    # Move the cursor to the beginning of the first prompt line and print the alert
    terminal_str += '\r' + alert_msg
    return terminal_str


def set_title_str(title: str) -> str:
    """Get the required string, including ANSI escape codes, for setting window title for the terminal.

    :param title: new title for the window
    :return string to write to sys.stderr in order to set the window title to the desired test
    """
    return colorama.ansi.set_title(title)
