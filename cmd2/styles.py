"""Defines custom Rich styles and their corresponding names for cmd2.

This module provides a centralized and discoverable way to manage Rich styles used
within the cmd2 framework. It defines a StrEnum for style names and a dictionary
that maps these names to their default style objects.
"""

import sys

from rich.style import (
    Style,
    StyleType,
)

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

from .colors import Color


class Cmd2Style(StrEnum):
    """An enumeration of the names of custom Rich styles used in cmd2.

    Using this enum allows for autocompletion and prevents typos when
    referencing cmd2-specific styles.

    This StrEnum is tightly coupled with DEFAULT_CMD2_STYLES. Any name
    added here must have a corresponding style definition there.
    """

    COMMAND_LINE = "cmd2.example"  # Command line examples in help text
    ERROR = "cmd2.error"  # Error text (used by perror())
    EXCEPTION_TYPE = "cmd2.exception.type"  # Used by pexcept to mark an exception type
    HELP_HEADER = "cmd2.help.header"  # Help table header text
    HELP_LEADER = "cmd2.help.leader"  # Text right before the help tables are listed
    SUCCESS = "cmd2.success"  # Success text (used by psuccess())
    TABLE_BORDER = "cmd2.table_border"  # Applied to cmd2's table borders
    WARNING = "cmd2.warning"  # Warning text (used by pwarning())


# Default styles used by cmd2. Tightly coupled with the Cmd2Style enum.
DEFAULT_CMD2_STYLES: dict[str, StyleType] = {
    Cmd2Style.COMMAND_LINE: Style(color=Color.CYAN, bold=True),
    Cmd2Style.ERROR: Style(color=Color.BRIGHT_RED),
    Cmd2Style.EXCEPTION_TYPE: Style(color=Color.DARK_ORANGE, bold=True),
    Cmd2Style.HELP_HEADER: Style(color=Color.BRIGHT_GREEN, bold=True),
    Cmd2Style.HELP_LEADER: Style(color=Color.CYAN, bold=True),
    Cmd2Style.SUCCESS: Style(color=Color.GREEN),
    Cmd2Style.TABLE_BORDER: Style(color=Color.BRIGHT_GREEN),
    Cmd2Style.WARNING: Style(color=Color.BRIGHT_YELLOW),
}
