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
)
from rich.padding import Padding
from rich.protocol import rich_cast
from rich.style import StyleType
from rich.table import (
    Column,
    Table,
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
    """Create a default theme for the application.

    This theme combines the default styles from cmd2, rich-argparse, and Rich.
    """
    app_styles = DEFAULT_CMD2_STYLES.copy()
    app_styles.update(RichHelpFormatter.styles.copy())
    return Theme(app_styles, inherit=True)


def set_theme(styles: Mapping[str, StyleType] | None = None) -> None:
    """Set the Rich theme used by cmd2.

    Call set_theme() with no arguments to reset to the default theme.
    This will clear any custom styles that were previously applied.

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


# The application-wide theme. You can change it with set_theme().
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


class Cmd2BaseConsole(Console):
    """Base class for all cmd2 Rich consoles.

    This class handles the core logic for managing Rich behavior based on
    cmd2's global settings, such as `ALLOW_STYLE` and `APP_THEME`.
    """

    def __init__(
        self,
        file: IO[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Cmd2BaseConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        :param kwargs: keyword arguments passed to the parent Console class.
        """
        # Don't allow force_terminal or force_interactive to be passed in, as their
        # behavior is controlled by the ALLOW_STYLE setting.
        if "force_terminal" in kwargs:
            raise TypeError(
                "Passing 'force_terminal' is not allowed. Its behavior is controlled by the 'ALLOW_STYLE' setting."
            )
        if "force_interactive" in kwargs:
            raise TypeError(
                "Passing 'force_interactive' is not allowed. Its behavior is controlled by the 'ALLOW_STYLE' setting."
            )

        # Don't allow a theme to be passed in, as it is controlled by the global APP_THEME.
        # Use cmd2.rich_utils.set_theme() to set the global theme or use a temporary
        # theme with console.use_theme().
        if "theme" in kwargs:
            raise TypeError(
                "Passing 'theme' is not allowed. Its behavior is controlled by the global APP_THEME and set_theme()."
            )

        force_terminal: bool | None = None
        force_interactive: bool | None = None

        if ALLOW_STYLE == AllowStyle.ALWAYS:
            force_terminal = True

            # Turn off interactive mode if dest is not actually a terminal which supports it
            tmp_console = Console(file=file)
            force_interactive = tmp_console.is_interactive
        elif ALLOW_STYLE == AllowStyle.NEVER:
            force_terminal = False

        super().__init__(
            file=file,
            force_terminal=force_terminal,
            force_interactive=force_interactive,
            theme=APP_THEME,
            **kwargs,
        )

    def on_broken_pipe(self) -> None:
        """Override which raises BrokenPipeError instead of SystemExit."""
        self.quiet = True
        raise BrokenPipeError


class Cmd2GeneralConsole(Cmd2BaseConsole):
    """Rich console for general-purpose printing."""

    def __init__(self, file: IO[str] | None = None) -> None:
        """Cmd2GeneralConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        """
        # This console is configured for general-purpose printing. It enables soft wrap
        # and disables Rich's automatic processing for markup, emoji, and highlighting.
        # These defaults can be overridden in calls to the console's or cmd2's print methods.
        super().__init__(
            file=file,
            soft_wrap=True,
            markup=False,
            emoji=False,
            highlight=False,
        )


class Cmd2RichArgparseConsole(Cmd2BaseConsole):
    """Rich console for rich-argparse output.

    This class ensures long lines in help text are not truncated by avoiding soft_wrap,
    which conflicts with rich-argparse's explicit no_wrap and overflow settings.
    """


class Cmd2ExceptionConsole(Cmd2BaseConsole):
    """Rich console for printing exceptions.

    Ensures that long exception messages word wrap for readability by keeping soft_wrap disabled.
    """


def console_width() -> int:
    """Return the width of the console."""
    return Cmd2BaseConsole().width


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


# If True, Rich still has the bug addressed in string_to_rich_text().
_from_ansi_has_newline_bug = Text.from_ansi("\n").plain == ""


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

    if _from_ansi_has_newline_bug:
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


def indent(renderable: RenderableType, level: int) -> Padding:
    """Indent a Rich renderable.

    When soft-wrapping is enabled, a Rich console is unable to properly print a
    Padding object of indented text, as it truncates long strings instead of wrapping
    them. This function provides a workaround for this issue, ensuring that indented
    text is printed correctly regardless of the soft-wrap setting.

    For non-text objects, this function merely serves as a convenience
    wrapper around Padding.indent().

    :param renderable: a Rich renderable to indent.
    :param level: number of characters to indent.
    :return: a Padding object containing the indented content.
    """
    if isinstance(renderable, (str, Text)):
        # Wrap text in a grid to handle the wrapping.
        text_grid = Table.grid(Column(overflow="fold"))
        text_grid.add_row(renderable)
        renderable = text_grid

    return Padding.indent(renderable, level)


def prepare_objects_for_rendering(*objects: Any) -> tuple[Any, ...]:
    """Prepare a tuple of objects for printing by Rich's Console.print().

    This function converts any non-Rich object whose string representation contains
    ANSI style codes into a rich.Text object. This ensures correct display width
    calculation, as Rich can then properly parse and account for the non-printing
    ANSI codes. All other objects are left untouched, allowing Rich's native
    renderers to handle them.

    :param objects: objects to prepare
    :return: a tuple containing the processed objects.
    """
    object_list = list(objects)

    for i, obj in enumerate(object_list):
        # Resolve the object's final renderable form, including those
        # with a __rich__ method that might return a string.
        renderable = rich_cast(obj)

        # This object implements the Rich console protocol, so no preprocessing is needed.
        if isinstance(renderable, ConsoleRenderable):
            continue

        # Check if the object's string representation contains ANSI styles, and if so,
        # replace it with a Rich Text object for correct width calculation.
        renderable_as_str = str(renderable)
        renderable_as_text = string_to_rich_text(renderable_as_str)

        if renderable_as_text.plain != renderable_as_str:
            object_list[i] = renderable_as_text

    return tuple(object_list)
