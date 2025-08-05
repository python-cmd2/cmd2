"""Provides common utilities to support Rich in cmd2 applications."""

from collections.abc import Mapping
from enum import Enum
from typing import (
    IO,
    Any,
    Optional,
    TypedDict,
)

from rich.console import (
    Console,
    ConsoleRenderable,
    JustifyMethod,
    OverflowMethod,
    RenderableType,
    RichCast,
)
from rich.style import (
    Style,
    StyleType,
)
from rich.text import Text
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


class RichPrintKwargs(TypedDict, total=False):
    """Keyword arguments that can be passed to rich.console.Console.print() via cmd2's print methods.

    See Rich's Console.print() documentation for full details on these parameters.
    https://rich.readthedocs.io/en/stable/reference/console.html#rich.console.Console.print

    Note: All fields are optional (total=False). If a key is not present in the
    dictionary, Rich's default behavior for that argument will apply.
    """

    justify: Optional[JustifyMethod]
    overflow: Optional[OverflowMethod]
    no_wrap: Optional[bool]
    markup: Optional[bool]
    emoji: Optional[bool]
    highlight: Optional[bool]
    width: Optional[int]
    height: Optional[int]
    crop: bool
    new_line_start: bool


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

        # Configure console defaults to treat output as plain, unstructured text.
        # This involves enabling soft wrapping (no automatic word-wrap) and disabling
        # Rich's automatic markup, emoji, and highlight processing.
        # While these automatic features are off by default, the console fully supports
        # rendering explicitly created Rich objects (e.g., Panel, Table).
        # Any of these default settings or other print behaviors can be overridden
        # in individual Console.print() calls or via cmd2's print methods.
        super().__init__(
            file=file,
            soft_wrap=True,
            markup=False,
            emoji=False,
            highlight=False,
            theme=THEME,
            **kwargs,
        )

    def on_broken_pipe(self) -> None:
        """Override which raises BrokenPipeError instead of SystemExit."""
        self.quiet = True
        raise BrokenPipeError


def from_ansi(text: str) -> Text:
    r"""Patched version of rich.Text.from_ansi() that handles a discarded newline issue.

    Text.from_ansi() currently removes the ending line break from string.
    e.g. "Hello\n" becomes "Hello"

    There is currently a pull request to fix this.
    https://github.com/Textualize/rich/pull/3793

    :param text: a string to convert to a Text object.
    :return: the converted string
    """
    result = Text.from_ansi(text)

    # If 'text' ends with a line break character, restore the missing newline to 'result'.
    # Note: '\r\n' is handled as its last character is '\n'.
    # Source: https://docs.python.org/3/library/stdtypes.html#str.splitlines
    line_break_chars = {
        "\n",  # Line Feed
        "\r",  # Carriage Return
        "\v",  # Vertical Tab
        "\f",  # Form Feed
        "\x1c",  # File Separator
        "\x1d",  # Group Separator
        "\x1e",  # Record Separator
        "\x85",  # Next Line (NEL)
        "\u2028",  # Line Separator
        "\u2029",  # Paragraph Separator
    }
    if text and text[-1] in line_break_chars:
        # We use "\n" because Text.from_ansi() converts all line breaks chars into newlines.
        result.append("\n")

    return result


def prepare_objects_for_rich_print(*objects: Any) -> tuple[RenderableType, ...]:
    """Prepare a tuple of objects for printing by Rich's Console.print().

    Converts any non-Rich objects (i.e., not ConsoleRenderable or RichCast)
    into rich.Text objects by stringifying them and processing them with
    from_ansi(). This ensures Rich correctly interprets any embedded ANSI
    escape sequences.

    :param objects: objects to prepare
    :return: a tuple containing the processed objects, where non-Rich objects are
             converted to rich.Text.
    """
    object_list = list(objects)
    for i, obj in enumerate(object_list):
        if not isinstance(obj, (ConsoleRenderable, RichCast)):
            object_list[i] = from_ansi(str(obj))
    return tuple(object_list)
