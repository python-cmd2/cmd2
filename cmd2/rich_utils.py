"""Provides common utilities to support Rich in cmd2 applications."""

from collections.abc import Mapping
from enum import Enum
from typing import (
    IO,
    Any,
    Optional,
)

from rich.console import Console
from rich.style import (
    Style,
    StyleType,
)
from rich.theme import Theme
from rich_argparse import RichHelpFormatter


class AllowStyle(Enum):
    """Values for ``cmd2.rich_utils.allow_style``."""

    ALWAYS = 'Always'  # Always output ANSI style sequences
    NEVER = 'Never'  # Remove ANSI style sequences from all output
    TERMINAL = 'Terminal'  # Remove ANSI style sequences if the output is not going to the terminal

    def __str__(self) -> str:
        """Return value instead of enum name for printing in cmd2's set command."""
        return str(self.value)

    def __repr__(self) -> str:
        """Return quoted value instead of enum description for printing in cmd2's set command."""
        return repr(self.value)


# Controls when ANSI style sequences are allowed in output
allow_style = AllowStyle.TERMINAL

# Default styles for cmd2
DEFAULT_CMD2_STYLES: dict[str, StyleType] = {
    "cmd2.success": Style(color="green"),
    "cmd2.warning": Style(color="bright_yellow"),
    "cmd2.error": Style(color="bright_red"),
    "cmd2.help_header": Style(color="bright_green", bold=True),
    "cmd2.example": Style(color="cyan", bold=True),
}

# Include default styles from RichHelpFormatter
DEFAULT_CMD2_STYLES.update(RichHelpFormatter.styles.copy())


class Cmd2Theme(Theme):
    """Rich theme class used by Cmd2Console."""

    def __init__(self, styles: Optional[Mapping[str, StyleType]] = None, inherit: bool = True) -> None:
        """Cmd2Theme initializer.

        :param styles: optional mapping of style names on to styles.
                       Defaults to None for a theme with no styles.
        :param inherit: Inherit default styles. Defaults to True.
        """
        cmd2_styles = DEFAULT_CMD2_STYLES.copy() if inherit else {}
        if styles is not None:
            cmd2_styles.update(styles)

        super().__init__(cmd2_styles, inherit=inherit)


# Current Rich theme used by Cmd2Console
THEME: Cmd2Theme = Cmd2Theme()


def set_theme(new_theme: Cmd2Theme) -> None:
    """Set the Rich theme used by Cmd2Console and rich-argparse.

    :param new_theme: new theme to use.
    """
    global THEME  # noqa: PLW0603
    THEME = new_theme

    # Make sure the new theme has all style names included in a Cmd2Theme.
    missing_names = Cmd2Theme().styles.keys() - THEME.styles.keys()
    for name in missing_names:
        THEME.styles[name] = Style()

    # Update rich-argparse styles
    for name in RichHelpFormatter.styles.keys() & THEME.styles.keys():
        RichHelpFormatter.styles[name] = THEME.styles[name]


class Cmd2Console(Console):
    """Rich console with characteristics appropriate for cmd2 applications."""

    def __init__(self, file: IO[str]) -> None:
        """Cmd2Console initializer.

        :param file: a file object where the console should write to
        """
        kwargs: dict[str, Any] = {}
        if allow_style == AllowStyle.ALWAYS:
            kwargs["force_terminal"] = True

            # Turn off interactive mode if dest is not actually a terminal which supports it
            tmp_console = Console(file=file)
            kwargs["force_interactive"] = tmp_console.is_interactive
        elif allow_style == AllowStyle.NEVER:
            kwargs["force_terminal"] = False

        # Turn off automatic markup, emoji, and highlight rendering at the console level.
        # You can still enable these in Console.print() calls.
        super().__init__(
            file=file,
            tab_size=4,
            markup=False,
            emoji=False,
            highlight=False,
            theme=THEME,
            **kwargs,
        )

    def on_broken_pipe(self) -> None:
        """Override which raises BrokenPipeError instead of SystemExit."""
        import contextlib

        with contextlib.suppress(SystemExit):
            super().on_broken_pipe()

        raise BrokenPipeError
