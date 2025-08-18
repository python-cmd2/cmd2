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

from .colors import ColorName


class Cmd2Style(StrEnum):
    """An enumeration of the names of custom Rich styles used in cmd2.

    Using this enum allows for autocompletion and prevents typos when
    referencing cmd2-specific styles.

    This StrEnum is tightly coupled with DEFAULT_CMD2_STYLES. Any name
    added here must have a corresponding style definition there.
    """

    ERROR = "cmd2.error"
    EXAMPLE = "cmd2.example"
    HELP_HEADER = "cmd2.help.header"
    HELP_TITLE = "cmd2.help.title"
    RULE_LINE = "cmd2.rule.line"
    SUCCESS = "cmd2.success"
    WARNING = "cmd2.warning"


# Default styles used by cmd2. Tightly coupled with the Cmd2Style enum.
DEFAULT_CMD2_STYLES: dict[str, StyleType] = {
    Cmd2Style.ERROR: Style(color=ColorName.BRIGHT_RED),
    Cmd2Style.EXAMPLE: Style(color=ColorName.CYAN, bold=True),
    Cmd2Style.HELP_HEADER: Style(color=ColorName.CYAN, bold=True),
    Cmd2Style.HELP_TITLE: Style(color=ColorName.BRIGHT_GREEN, bold=True),
    Cmd2Style.RULE_LINE: Style(color=ColorName.BRIGHT_GREEN),
    Cmd2Style.SUCCESS: Style(color=ColorName.GREEN),
    Cmd2Style.WARNING: Style(color=ColorName.BRIGHT_YELLOW),
}
