r"""Support for terminal control escape sequences.

These are used for things like setting the window title and asynchronous alerts.
"""

from . import string_utils as su

#######################################################
# Common ANSI escape sequence constants
#######################################################
ESC = '\x1b'
CSI = f'{ESC}['
OSC = f'{ESC}]'
BEL = '\a'


####################################################################################
# Utility functions which create various ANSI sequences
####################################################################################
def set_title_str(title: str) -> str:
    """Generate a string that, when printed, sets a terminal's window title.

    :param title: new title for the window
    :return: the set title string
    """
    return f"{OSC}2;{title}{BEL}"


def clear_screen_str(clear_type: int = 2) -> str:
    """Generate a string that, when printed, clears a terminal screen based on value of clear_type.

    :param clear_type: integer which specifies how to clear the screen (Defaults to 2)
                       Possible values:
                       0 - clear from cursor to end of screen
                       1 - clear from cursor to beginning of the screen
                       2 - clear entire screen
                       3 - clear entire screen and delete all lines saved in the scrollback buffer
    :return: the clear screen string
    :raises ValueError: if clear_type is not a valid value
    """
    if 0 <= clear_type <= 3:
        return f"{CSI}{clear_type}J"
    raise ValueError("clear_type must in an integer from 0 to 3")


def clear_line_str(clear_type: int = 2) -> str:
    """Generate a string that, when printed, clears a line based on value of clear_type.

    :param clear_type: integer which specifies how to clear the line (Defaults to 2)
                       Possible values:
                       0 - clear from cursor to the end of the line
                       1 - clear from cursor to beginning of the line
                       2 - clear entire line
    :return: the clear line string
    :raises ValueError: if clear_type is not a valid value
    """
    if 0 <= clear_type <= 2:
        return f"{CSI}{clear_type}K"
    raise ValueError("clear_type must in an integer from 0 to 2")


####################################################################################
# Implementations intended for direct use (do NOT use outside of cmd2)
####################################################################################
class Cursor:
    """Create ANSI sequences to alter the cursor position."""

    @staticmethod
    def UP(count: int = 1) -> str:  # noqa: N802
        """Move the cursor up a specified amount of lines (Defaults to 1)."""
        return f"{CSI}{count}A"

    @staticmethod
    def DOWN(count: int = 1) -> str:  # noqa: N802
        """Move the cursor down a specified amount of lines (Defaults to 1)."""
        return f"{CSI}{count}B"

    @staticmethod
    def FORWARD(count: int = 1) -> str:  # noqa: N802
        """Move the cursor forward a specified amount of lines (Defaults to 1)."""
        return f"{CSI}{count}C"

    @staticmethod
    def BACK(count: int = 1) -> str:  # noqa: N802
        """Move the cursor back a specified amount of lines (Defaults to 1)."""
        return f"{CSI}{count}D"

    @staticmethod
    def SET_POS(x: int, y: int) -> str:  # noqa: N802
        """Set the cursor position to coordinates which are 1-based."""
        return f"{CSI}{y};{x}H"


def async_alert_str(*, terminal_columns: int, prompt: str, line: str, cursor_offset: int, alert_msg: str) -> str:
    """Calculate the desired string, including ANSI escape codes, for displaying an asynchronous alert message.

    :param terminal_columns: terminal width (number of columns)
    :param prompt: current onscreen prompt
    :param line: current contents of the Readline line buffer
    :param cursor_offset: the offset of the current cursor position within line
    :param alert_msg: the message to display to the user
    :return: the correct string so that the alert message appears to the user to be printed above the current line.
    """
    # Split the prompt lines since it can contain newline characters.
    prompt_lines = prompt.splitlines() or ['']

    # Calculate how many terminal lines are taken up by all prompt lines except for the last one.
    # That will be included in the input lines calculations since that is where the cursor is.
    num_prompt_terminal_lines = 0
    for prompt_line in prompt_lines[:-1]:
        prompt_line_width = su.str_width(prompt_line)
        num_prompt_terminal_lines += int(prompt_line_width / terminal_columns) + 1

    # Now calculate how many terminal lines are take up by the input
    last_prompt_line = prompt_lines[-1]
    last_prompt_line_width = su.str_width(last_prompt_line)

    input_width = last_prompt_line_width + su.str_width(line)

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
    terminal_str += (clear_line_str() + Cursor.UP(1)) * (total_lines - 1)

    # Clear the first prompt line
    terminal_str += clear_line_str()

    # Move the cursor to the beginning of the first prompt line and print the alert
    terminal_str += '\r' + alert_msg
    return terminal_str
