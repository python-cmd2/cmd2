"""Provides common utilities to support Rich in cmd2-based applications."""

import re
from collections.abc import (
    Iterable,
    Mapping,
)
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
from rich.pretty import is_expandable
from rich.protocol import rich_cast
from rich.segment import Segment
from rich.style import StyleType
from rich.table import (
    Column,
    Table,
)
from rich.text import Text
from rich.theme import Theme
from rich_argparse import RichHelpFormatter

from .styles import DEFAULT_CMD2_STYLES

# A compiled regular expression to detect ANSI style sequences.
ANSI_STYLE_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;?]*m")


class AllowStyle(Enum):
    """Values for ``cmd2.rich_utils.ALLOW_STYLE``."""

    ALWAYS = "Always"  # Always output ANSI style sequences
    NEVER = "Never"  # Remove ANSI style sequences from all output
    TERMINAL = "Terminal"  # Remove ANSI style sequences if the output is not going to the terminal

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
        :raises TypeError: if disallowed keyword argument is passed in.
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
        # and disables Rich's automatic detection for markup, emoji, and highlighting.
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

    def __init__(self, file: IO[str] | None = None) -> None:
        """Cmd2RichArgparseConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        """
        # Since this console is used to print error messages which may not have
        # been pre-formatted by rich-argparse, disable Rich's automatic detection
        # for markup, emoji, and highlighting. rich-argparse does markup and
        # highlighting without involving the console so these won't affect its
        # internal functionality.
        super().__init__(
            file=file,
            markup=False,
            emoji=False,
            highlight=False,
        )


class Cmd2ExceptionConsole(Cmd2BaseConsole):
    """Rich console for printing exceptions.

    Ensures that long exception messages word wrap for readability by keeping soft_wrap disabled.
    """


def console_width() -> int:
    """Return the width of the console."""
    return Console().width


def rich_text_to_string(text: Text) -> str:
    """Convert a Rich Text object to a string.

    This function's purpose is to render a Rich Text object, including any styles (e.g., color, bold),
    to a plain Python string with ANSI style sequences. It differs from `text.plain`, which strips
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

    This function processes objects to ensure they are rendered correctly by Rich.
    It inspects each object and, if its string representation contains ANSI style
    sequences, it converts the object to a Rich Text object. This ensures Rich can
    properly parse the non-printing codes for accurate display width calculation.

    Objects that already implement the Rich console protocol or are expandable
    by its pretty printer are left untouched, as they can be handled directly by
    Rich's native renderers.

    :param objects: objects to prepare
    :return: a tuple containing the processed objects.
    """
    object_list = list(objects)

    for i, obj in enumerate(object_list):
        # Resolve the object's final renderable form, including those
        # with a __rich__ method that might return a string.
        renderable = rich_cast(obj)

        # No preprocessing is needed for Rich-compatible or expandable objects.
        if isinstance(renderable, ConsoleRenderable) or is_expandable(renderable):
            continue

        # Check for ANSI style sequences in its string representation.
        renderable_as_str = str(renderable)
        if ANSI_STYLE_SEQUENCE_RE.search(renderable_as_str):
            object_list[i] = Text.from_ansi(renderable_as_str)

    return tuple(object_list)


###################################################################################
# Rich Library Monkey Patches
#
# These patches fix specific bugs in the Rich library. They are conditional and
# will only be applied if the bug is detected. When the bugs are fixed in a
# future Rich release, these patches and their corresponding tests should be
# removed.
###################################################################################

###################################################################################
# Text.from_ansi() monkey patch
###################################################################################

# Save original Text.from_ansi() so we can call it in our wrapper
_orig_text_from_ansi = Text.from_ansi


@classmethod  # type: ignore[misc]
def _from_ansi_wrapper(cls: type[Text], text: str, *args: Any, **kwargs: Any) -> Text:  # noqa: ARG001
    r"""Wrap Text.from_ansi() to fix its trailing newline bug.

    This wrapper handles an issue where Text.from_ansi() removes the
    trailing line break from a string (e.g. "Hello\n" becomes "Hello").

    There is currently a pull request on Rich to fix this.
    https://github.com/Textualize/rich/pull/3793
    """
    result = _orig_text_from_ansi(text, *args, **kwargs)

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


def _from_ansi_has_newline_bug() -> bool:
    """Check if Test.from_ansi() strips the trailing line break from a string."""
    return Text.from_ansi("\n") == Text.from_ansi("")


# Only apply the monkey patch if the bug is present
if _from_ansi_has_newline_bug():
    Text.from_ansi = _from_ansi_wrapper  # type: ignore[assignment]


###################################################################################
# Segment.apply_style() monkey patch
###################################################################################

# Save original Segment.apply_style() so we can call it in our wrapper
_orig_segment_apply_style = Segment.apply_style


@classmethod  # type: ignore[misc]
def _apply_style_wrapper(cls: type[Segment], *args: Any, **kwargs: Any) -> Iterable["Segment"]:
    r"""Wrap Segment.apply_style() to fix bug with styling newlines.

    This wrapper handles an issue where Segment.apply_style() includes newlines
    within styled Segments. As a result, when printing text using a background color
    and soft wrapping, the background color incorrectly carries over onto the following line.

    You can reproduce this behavior by calling console.print() using a background color
    and soft wrapping.

    For example:
        console.print("line_1", style="blue on white", soft_wrap=True)

    When soft wrapping is disabled, console.print() splits Segments into their individual
    lines, which separates the newlines from the styled text. Therefore, the background color
    issue does not occur in that mode.

    This function copies that behavior to fix this the issue even when soft wrapping is enabled.

    There is currently a pull request on Rich to fix this.
    https://github.com/Textualize/rich/pull/3839
    """
    styled_segments = list(_orig_segment_apply_style(*args, **kwargs))
    newline_segment = cls.line()

    # If the final segment ends in a newline, that newline will be stripped by Segment.split_lines().
    # Save an unstyled newline to restore later.
    end_segment = newline_segment if styled_segments and styled_segments[-1].text.endswith("\n") else None

    # Use Segment.split_lines() to separate the styled text from the newlines.
    # This way the ANSI reset code will appear before any newline.
    sanitized_segments: list[Segment] = []

    lines = list(Segment.split_lines(styled_segments))
    for index, line in enumerate(lines):
        sanitized_segments.extend(line)
        if index < len(lines) - 1:
            sanitized_segments.append(newline_segment)

    if end_segment is not None:
        sanitized_segments.append(end_segment)

    return sanitized_segments


def _rich_has_styled_newline_bug() -> bool:
    """Check if newlines are styled when soft wrapping."""
    console = Console(force_terminal=True)
    with console.capture() as capture:
        console.print("line_1", style="blue on white", soft_wrap=True)

    # Check if we see a styled newline in the output
    return "\x1b[34;47m\n\x1b[0m" in capture.get()


# Only apply the monkey patch if the bug is present
if _rich_has_styled_newline_bug():
    Segment.apply_style = _apply_style_wrapper  # type: ignore[assignment]
