"""Provides common utilities to support Rich in cmd2-based applications."""

from collections.abc import Mapping
from enum import Enum
from typing import (
    IO,
    Any,
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
    StyleType,
)
from rich.text import Text
from rich.theme import Theme
from rich_argparse import RichHelpFormatter

from .styles import DEFAULT_CMD2_STYLES


class AllowStyle(Enum):
    """Values for ``cmd2.rich_utils.ALLOW_STYLE``."""

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
ALLOW_STYLE = AllowStyle.TERMINAL


def _create_default_theme() -> Theme:
    """Create a default theme for cmd2-based applications.

    This theme combines the default styles from cmd2, rich-argparse, and Rich.
    """
    app_styles = DEFAULT_CMD2_STYLES.copy()
    app_styles.update(RichHelpFormatter.styles.copy())
    return Theme(app_styles, inherit=True)


def set_theme(styles: Mapping[str, StyleType] | None = None) -> None:
    """Set the Rich theme used by cmd2.

    :param styles: optional mapping of style names to styles
    """
    global APP_THEME  # noqa: PLW0603

    # Start with a fresh copy of the default styles.
    app_styles: dict[str, StyleType] = {}
    app_styles.update(_create_default_theme().styles)

    # Incorporate custom styles.
    if styles is not None:
        app_styles.update(styles)

    APP_THEME = Theme(app_styles)

    # Synchronize rich-argparse styles with the main application theme.
    for name in RichHelpFormatter.styles.keys() & APP_THEME.styles.keys():
        RichHelpFormatter.styles[name] = APP_THEME.styles[name]


# The main theme for cmd2-based applications.
# You can change it with set_theme().
APP_THEME = _create_default_theme()


class RichPrintKwargs(TypedDict, total=False):
    """Keyword arguments that can be passed to rich.console.Console.print() via cmd2's print methods.

    See Rich's Console.print() documentation for full details on these parameters.
    https://rich.readthedocs.io/en/stable/reference/console.html#rich.console.Console.print

    Note: All fields are optional (total=False). If a key is not present in the
    dictionary, Rich's default behavior for that argument will apply.
    """

    justify: JustifyMethod | None
    overflow: OverflowMethod | None
    no_wrap: bool | None
    markup: bool | None
    emoji: bool | None
    highlight: bool | None
    width: int | None
    height: int | None
    crop: bool
    new_line_start: bool


class Cmd2Console(Console):
    """Rich console with characteristics appropriate for cmd2-based applications."""

    def __init__(self, file: IO[str] | None = None) -> None:
        """Cmd2Console initializer.

        :param file: Optional file object where the console should write to. Defaults to sys.stdout.
        """
        force_terminal: bool | None = None
        force_interactive: bool | None = None

        if ALLOW_STYLE == AllowStyle.ALWAYS:
            force_terminal = True

            # Turn off interactive mode if dest is not actually a terminal which supports it
            tmp_console = Console(file=file)
            force_interactive = tmp_console.is_interactive
        elif ALLOW_STYLE == AllowStyle.NEVER:
            force_terminal = False

        # Configure console defaults to treat output as plain, unstructured text.
        # This involves enabling soft wrapping (no automatic word-wrap) and disabling
        # Rich's automatic markup, emoji, and highlight processing.
        # While these automatic features are off by default, the console fully supports
        # rendering explicitly created Rich objects (e.g., Panel, Table).
        # Any of these default settings or other print behaviors can be overridden
        # in individual Console.print() calls or via cmd2's print methods.
        super().__init__(
            file=file,
            force_terminal=force_terminal,
            force_interactive=force_interactive,
            soft_wrap=True,
            markup=False,
            emoji=False,
            highlight=False,
            theme=APP_THEME,
        )

    def on_broken_pipe(self) -> None:
        """Override which raises BrokenPipeError instead of SystemExit."""
        self.quiet = True
        raise BrokenPipeError


def console_width() -> int:
    """Return the width of the console."""
    return Cmd2Console().width


def rich_text_to_string(text: Text) -> str:
    """Convert a Rich Text object to a string.

    This function's purpose is to render a Rich Text object, including any styles (e.g., color, bold),
    to a plain Python string with ANSI escape codes. It differs from `text.plain`, which strips
    all formatting.

    :param text: the text object to convert
    :return: the resulting string with ANSI styles preserved.
    """
    console = Console(
        force_terminal=True,
        soft_wrap=True,
        no_color=False,
        markup=False,
        emoji=False,
        highlight=False,
        theme=APP_THEME,
    )
    with console.capture() as capture:
        console.print(text, end="")
    return capture.get()


def string_to_rich_text(text: str) -> Text:
    r"""Create a Text object from a string which can contain ANSI escape codes.

    This wraps rich.Text.from_ansi() to handle an issue where it removes the
    trailing line break from a string (e.g. "Hello\n" becomes "Hello").

    There is currently a pull request to fix this.
    https://github.com/Textualize/rich/pull/3793

    :param text: a string to convert to a Text object.
    :return: the converted string
    """
    result = Text.from_ansi(text)

    # If the original string ends with a recognized line break character,
    # then restore the missing newline. We use "\n" because Text.from_ansi()
    # converts all line breaks into newlines.
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
            object_list[i] = string_to_rich_text(str(obj))
    return tuple(object_list)
