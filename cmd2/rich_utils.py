"""Provides common utilities to support Rich in cmd2-based applications."""

import argparse
import re
import sys
import threading
from collections.abc import (
    Iterator,
    Mapping,
)
from enum import Enum
from typing import (
    IO,
    Any,
    ClassVar,
    TypedDict,
)

from rich.box import SIMPLE_HEAD
from rich.console import (
    Console,
    ConsoleOptions,
    ConsoleRenderable,
    Group,
    JustifyMethod,
    OverflowMethod,
    RenderableType,
    RenderResult,
)
from rich.padding import Padding
from rich.pretty import is_expandable
from rich.protocol import rich_cast
from rich.style import StyleType
from rich.table import (
    Column,
    Table,
)
from rich.text import Text
from rich.theme import Theme
from rich_argparse import (
    ArgumentDefaultsRichHelpFormatter,
    MetavarTypeRichHelpFormatter,
    RawDescriptionRichHelpFormatter,
    RawTextRichHelpFormatter,
    RichHelpFormatter,
)

from . import constants
from .styles import (
    DEFAULT_ARGPARSE_STYLES,
    DEFAULT_CMD2_STYLES,
    Cmd2Style,
)

# Matches ANSI SGR (Select Graphic Rendition) sequences for text styling.
# \x1b[   - the CSI (Control Sequence Introducer)
# [0-9;]* - zero or more digits or semicolons (parameters for the style)
# m       - the SGR final character
ANSI_STYLE_SEQUENCE_RE = re.compile(r"\x1b\[[0-9;]*m")


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


class Cmd2HelpFormatter(RichHelpFormatter):
    """Custom help formatter to configure ordering of help text."""

    # Have our own copy of the styles so set_theme() can synchronize them with
    # the cmd2 application theme without overwriting RichHelpFormatter's defaults.
    styles: ClassVar[dict[str, StyleType]] = DEFAULT_ARGPARSE_STYLES.copy()

    # Disable automatic highlighting in the help text.
    highlights: ClassVar[list[str]] = []

    # Disable markup rendering in usage, help, description, and epilog text.
    # cmd2's built-in commands do not escape opening brackets in their help text
    # and therefore rely on these settings being False. If you desire to use
    # markup in your help text, inherit from Cmd2HelpFormatter and override
    # these settings in that child class.
    usage_markup: ClassVar[bool] = False
    help_markup: ClassVar[bool] = False
    text_markup: ClassVar[bool] = False

    def __init__(
        self,
        prog: str,
        indent_increment: int = 2,
        max_help_position: int = 24,
        width: int | None = None,
        *,
        console: "Cmd2RichArgparseConsole | None" = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Cmd2HelpFormatter."""
        super().__init__(prog, indent_increment, max_help_position, width, console=console, **kwargs)

        # Recast to assist type checkers
        self._console: Cmd2RichArgparseConsole | None

    @property  # type: ignore[override]
    def console(self) -> "Cmd2RichArgparseConsole":
        """Return our console instance."""
        if self._console is None:
            self._console = Cmd2RichArgparseConsole()
        return self._console

    @console.setter
    def console(self, console: "Cmd2RichArgparseConsole") -> None:
        """Set our console instance."""
        self._console = console

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """Provide this help formatter to renderables via the console."""
        if isinstance(console, Cmd2RichArgparseConsole):
            old_formatter = console.help_formatter
            console.help_formatter = self
            try:
                yield from super().__rich_console__(console, options)
            finally:
                console.help_formatter = old_formatter
        else:
            # Handle rendering on a console type other than Cmd2RichArgparseConsole.
            # In this case, we don't set the help_formatter on the console.
            yield from super().__rich_console__(console, options)

    def _set_color(self, color: bool, **kwargs: Any) -> None:
        """Set the color for the help output.

        This override is needed because Python 3.15 added a 'file' keyword argument
        to _set_color() which some versions of RichHelpFormatter don't support.
        """
        # Argparse didn't add color support until 3.14
        if sys.version_info < (3, 14):
            return

        try:  # type: ignore[unreachable]
            super()._set_color(color, **kwargs)
        except TypeError:
            # Fallback for older versions of RichHelpFormatter that don't support keyword arguments
            super()._set_color(color)

    def _build_nargs_range_str(self, nargs_range: tuple[int, int | float]) -> str:
        """Build nargs range string for help text."""
        if nargs_range[1] == constants.INFINITY:
            # {min+}
            range_str = f"{{{nargs_range[0]}+}}"
        else:
            # {min..max}
            range_str = f"{{{nargs_range[0]}..{nargs_range[1]}}}"

        return range_str

    def _format_args(self, action: argparse.Action, default_metavar: str) -> str:
        """Override to handle cmd2's custom nargs formatting.

        All formats in this function need to be handled by _rich_metavar_parts().
        """
        get_metavar = self._metavar_formatter(action, default_metavar)

        # Handle nargs specified as a range
        nargs_range = action.get_nargs_range()  # type: ignore[attr-defined]
        if nargs_range is not None:
            arg_str = "%s" % get_metavar(1)  # noqa: UP031
            range_str = self._build_nargs_range_str(nargs_range)
            return f"{arg_str}{range_str}"

        # When nargs is just a number, argparse repeats the arg in the help text.
        # For instance, when nargs=5 the help text looks like: 'command arg arg arg arg arg'.
        # To make this less verbose, format it like: 'command arg{5}'.
        # Do not customize the output when metavar is a tuple of strings. Allow argparse's
        # formatter to handle that instead.
        if not isinstance(action.metavar, tuple) and isinstance(action.nargs, int) and action.nargs > 1:
            arg_str = "%s" % get_metavar(1)  # noqa: UP031
            return f"{arg_str}{{{action.nargs}}}"

        # Fallback to parent for all other cases
        return super()._format_args(action, default_metavar)

    def _rich_metavar_parts(
        self,
        action: argparse.Action,
        default_metavar: str,
    ) -> Iterator[tuple[str, bool]]:
        """Override to handle all cmd2-specific formatting in _format_args()."""
        get_metavar = self._metavar_formatter(action, default_metavar)

        # Handle nargs specified as a range
        nargs_range = action.get_nargs_range()  # type: ignore[attr-defined]
        if nargs_range is not None:
            yield "%s" % get_metavar(1), True  # noqa: UP031
            yield self._build_nargs_range_str(nargs_range), False
            return

        # Handle specific integer nargs (e.g., nargs=5 -> arg{5})
        if not isinstance(action.metavar, tuple) and isinstance(action.nargs, int) and action.nargs > 1:
            yield "%s" % get_metavar(1), True  # noqa: UP031
            yield f"{{{action.nargs}}}", False
            return

        # Fallback to parent for all other cases
        yield from super()._rich_metavar_parts(action, default_metavar)


class RawDescriptionCmd2HelpFormatter(
    RawDescriptionRichHelpFormatter,
    Cmd2HelpFormatter,
):
    """Cmd2 help message formatter which retains any formatting in descriptions and epilogs."""


class RawTextCmd2HelpFormatter(
    RawTextRichHelpFormatter,
    Cmd2HelpFormatter,
):
    """Cmd2 help message formatter which retains formatting of all help text."""


class ArgumentDefaultsCmd2HelpFormatter(
    ArgumentDefaultsRichHelpFormatter,
    Cmd2HelpFormatter,
):
    """Cmd2 help message formatter which adds default values to argument help."""


class MetavarTypeCmd2HelpFormatter(
    MetavarTypeRichHelpFormatter,
    Cmd2HelpFormatter,
):
    """Cmd2 help message formatter which uses the argument 'type' as the default
    metavar value (instead of the argument 'dest').
    """  # noqa: D205


class TextGroup:
    """A block of text which is formatted like an argparse argument group, including a title.

    Title:
      Here is the first row of text.
      Here is yet another row of text.
    """

    def __init__(
        self,
        title: str,
        text: RenderableType,
    ) -> None:
        """TextGroup initializer.

        :param title: the group's title
        :param text: the group's text (string or object that may be rendered by Rich)
        """
        self.title = title
        self.text = text

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """Return a renderable Rich Group object for the class instance.

        This method formats the title and indents the text to match argparse
        group styling, making the object displayable by a Rich console.
        """
        formatter: Cmd2HelpFormatter | None = None
        if isinstance(console, Cmd2RichArgparseConsole):
            formatter = console.help_formatter

        # This occurs if the console is not a Cmd2RichArgparseConsole or if the
        # TextGroup is printed directly instead of as part of an argparse help message.
        if formatter is None:
            # If console is the wrong type, then have Cmd2HelpFormatter create its own.
            formatter = Cmd2HelpFormatter(
                prog="",
                console=console if isinstance(console, Cmd2RichArgparseConsole) else None,
            )

        styled_title = Text(
            type(formatter).group_name_formatter(f"{self.title}:"),
            style=formatter.styles["argparse.groups"],
        )

        # Indent text like an argparse argument group does
        indented_text = indent(self.text, formatter._indent_increment)

        yield Group(styled_title, indented_text)


# The application-wide theme. Use get_theme() and set_theme() to access it.
_APP_THEME: Theme | None = None


def get_theme() -> Theme:
    """Get the application-wide theme. Initializes it on the first call."""
    global _APP_THEME  # noqa: PLW0603
    if _APP_THEME is None:
        _APP_THEME = _create_default_theme()
    return _APP_THEME


def set_theme(styles: Mapping[str, StyleType] | None = None) -> None:
    """Set the Rich theme used by cmd2.

    This function performs an in-place update of the existing theme's
    styles. This ensures that any Console objects already using the theme
    will reflect the changes immediately without needing to be recreated.

    Call set_theme() with no arguments to reset to the default theme.
    This will clear any custom styles that were previously applied.

    :param styles: optional mapping of style names to styles
    """
    theme = get_theme()

    # Start with a fresh copy of the default styles.
    unparsed_styles: dict[str, StyleType] = {}
    unparsed_styles.update(_create_default_theme().styles)

    # Add the custom styles, which may contain unparsed strings
    if styles is not None:
        unparsed_styles.update(styles)

    # Use Rich's Theme class to perform the parsing
    parsed_styles = Theme(unparsed_styles).styles

    # Perform the in-place update with the results
    theme.styles.clear()
    theme.styles.update(parsed_styles)

    # Synchronize rich-argparse styles with the main application theme.
    for name in Cmd2HelpFormatter.styles.keys() & theme.styles.keys():
        Cmd2HelpFormatter.styles[name] = theme.styles[name]


def _create_default_theme() -> Theme:
    """Create a default theme for the application.

    This theme combines the default styles from cmd2, rich-argparse, and Rich.
    """
    app_styles = DEFAULT_CMD2_STYLES.copy()
    app_styles.update(DEFAULT_ARGPARSE_STYLES)
    return Theme(app_styles, inherit=True)


class Cmd2BaseConsole(Console):
    """Base class for all cmd2 Rich consoles.

    This class handles the core logic for managing Rich behavior based on
    cmd2's global settings, such as ALLOW_STYLE and the application theme.
    """

    def __init__(
        self,
        *,
        file: IO[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Cmd2BaseConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        :param kwargs: keyword arguments passed to the parent Console class.
        :raises TypeError: if disallowed keyword argument is passed in.
        """
        # These settings are controlled by the ALLOW_STYLE setting and cannot be overridden.
        if "color_system" in kwargs:
            raise TypeError("Passing 'color_system' is not allowed. Its behavior is controlled by the 'ALLOW_STYLE' setting.")
        if "force_terminal" in kwargs:
            raise TypeError(
                "Passing 'force_terminal' is not allowed. Its behavior is controlled by the 'ALLOW_STYLE' setting."
            )
        if "force_interactive" in kwargs:
            raise TypeError(
                "Passing 'force_interactive' is not allowed. Its behavior is controlled by the 'ALLOW_STYLE' setting."
            )

        # Don't allow a theme to be passed in, as it is controlled by get_theme() and set_theme().
        # Use cmd2.rich_utils.set_theme() to set the global theme or use a temporary
        # theme with console.use_theme().
        if "theme" in kwargs:
            raise TypeError("Passing 'theme' is not allowed. Its behavior is controlled by get_theme() and set_theme().")

        # Store the configuration key used by cmd2 to cache this console.
        self._config_key = self._build_config_key(file=file, **kwargs)

        force_terminal: bool | None = None
        force_interactive: bool | None = None
        allow_style = False

        if ALLOW_STYLE == AllowStyle.ALWAYS:
            force_terminal = True
            allow_style = True

            # Turn off interactive mode if dest is not a terminal which supports it.
            tmp_console = Console(file=file)
            force_interactive = tmp_console.is_interactive
        elif ALLOW_STYLE == AllowStyle.TERMINAL:
            tmp_console = Console(file=file)
            allow_style = tmp_console.is_terminal
        elif ALLOW_STYLE == AllowStyle.NEVER:
            force_terminal = False

        super().__init__(
            file=file,
            color_system="truecolor" if allow_style else None,
            force_terminal=force_terminal,
            force_interactive=force_interactive,
            theme=get_theme(),
            **kwargs,
        )

    @staticmethod
    def _build_config_key(
        *,
        file: IO[str] | None,
        **kwargs: Any,
    ) -> tuple[Any, ...]:
        """Build a key representing the settings used to initialize a console.

        This key includes the file identity, global settings (ALLOW_STYLE, application theme),
        and any other settings passed in via kwargs.

        :param file: file stream being checked
        :param kwargs: other console settings
        """
        return (
            id(file),
            ALLOW_STYLE,
            id(get_theme()),
            tuple(sorted(kwargs.items())),
        )

    def matches_config(
        self,
        *,
        file: IO[str] | None,
        **kwargs: Any,
    ) -> bool:
        """Check if this console instance was initialized with the specified settings.

        :param file: file stream being checked
        :param kwargs: other console settings being checked
        :return: True if the settings match this console's configuration
        """
        return self._config_key == self._build_config_key(file=file, **kwargs)

    def on_broken_pipe(self) -> None:
        """Override which raises BrokenPipeError instead of SystemExit."""
        self.quiet = True
        raise BrokenPipeError

    def print(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = None,
        justify: JustifyMethod | None = None,
        overflow: OverflowMethod | None = None,
        no_wrap: bool | None = None,
        emoji: bool | None = None,
        markup: bool | None = None,
        highlight: bool | None = None,
        width: int | None = None,
        height: int | None = None,
        crop: bool = True,
        soft_wrap: bool | None = None,
        new_line_start: bool = False,
    ) -> None:
        """Override to support ANSI sequences.

        This method calls [cmd2.rich_utils.prepare_objects_for_rendering][] on the
        objects being printed. This ensures that strings containing ANSI style
        sequences are converted to Rich Text objects, so that Rich can correctly
        calculate their display width.
        """
        prepared_objects = prepare_objects_for_rendering(*objects)

        super().print(
            *prepared_objects,
            sep=sep,
            end=end,
            style=style,
            justify=justify,
            overflow=overflow,
            no_wrap=no_wrap,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            width=width,
            height=height,
            crop=crop,
            soft_wrap=soft_wrap,
            new_line_start=new_line_start,
        )

    def log(
        self,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        style: StyleType | None = None,
        justify: JustifyMethod | None = None,
        emoji: bool | None = None,
        markup: bool | None = None,
        highlight: bool | None = None,
        log_locals: bool = False,
        _stack_offset: int = 1,
    ) -> None:
        """Override to support ANSI sequences.

        This method calls [cmd2.rich_utils.prepare_objects_for_rendering][] on the
        objects being logged. This ensures that strings containing ANSI style
        sequences are converted to Rich Text objects, so that Rich can correctly
        calculate their display width.
        """
        prepared_objects = prepare_objects_for_rendering(*objects)

        # Increment _stack_offset because we added this wrapper frame
        super().log(
            *prepared_objects,
            sep=sep,
            end=end,
            style=style,
            justify=justify,
            emoji=emoji,
            markup=markup,
            highlight=highlight,
            log_locals=log_locals,
            _stack_offset=_stack_offset + 1,
        )


class Cmd2GeneralConsole(Cmd2BaseConsole):
    """Rich console for general-purpose printing.

    It enables soft wrap and disables Rich's automatic detection
    for markup, emoji, and highlighting.
    """

    def __init__(self, *, file: IO[str] | None = None) -> None:
        """Cmd2GeneralConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        """
        super().__init__(
            file=file,
            soft_wrap=True,
            markup=False,
            emoji=False,
            highlight=False,
        )


class Cmd2RichArgparseConsole(Cmd2BaseConsole):
    """Rich console for rich-argparse output.

    Ensures long lines in help text are not truncated by disabling soft_wrap,
    which conflicts with rich-argparse's explicit no_wrap and overflow settings.

    Since this console is used to print error messages which may not be intended
    for Rich formatting, it disables Rich's automatic detection for markup, emoji,
    and highlighting. Because rich-argparse does markup and highlighting without
    involving the console, disabling these settings does not affect the library's
    internal functionality.

    Additionally, this console serves as a context carrier for the active help formatter,
    allowing renderables to access formatting settings during help generation.
    """

    def __init__(self, *, file: IO[str] | None = None) -> None:
        """Cmd2RichArgparseConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        """
        super().__init__(
            file=file,
            soft_wrap=False,
            markup=False,
            emoji=False,
            highlight=False,
        )
        self._thread_local = threading.local()

    @property
    def help_formatter(self) -> "Cmd2HelpFormatter | None":
        """Return the active help formatter for this thread."""
        return getattr(self._thread_local, "help_formatter", None)

    @help_formatter.setter
    def help_formatter(self, value: "Cmd2HelpFormatter | None") -> None:
        """Set the active help formatter for this thread."""
        self._thread_local.help_formatter = value


class Cmd2ExceptionConsole(Cmd2BaseConsole):
    """Rich console for printing exceptions and Rich Tracebacks.

    Ensures that output is always word-wrapped for readability and disables
    Rich's automatic detection for markup, emoji, and highlighting to prevent
    interference with raw error data.
    """

    def __init__(self, *, file: IO[str] | None = None) -> None:
        """Cmd2ExceptionConsole initializer.

        :param file: optional file object where the console should write to.
                     Defaults to sys.stdout.
        """
        super().__init__(
            file=file,
            soft_wrap=False,
            markup=False,
            emoji=False,
            highlight=False,
        )


class RichPrintKwargs(TypedDict, total=False):
    """Infrequently used Rich Console.print() keyword arguments.

    These arguments are supported by cmd2's print methods (e.g., poutput())
    via their ``rich_print_kwargs`` parameter.

    See Rich's Console.print() documentation for full details:
    https://rich.readthedocs.io/en/stable/reference/console.html#rich.console.Console.print

    Note: All fields are optional (total=False). If a key is not present,
    Rich's default behavior for that argument will apply.
    """

    overflow: OverflowMethod | None
    no_wrap: bool | None
    width: int | None
    height: int | None
    crop: bool
    new_line_start: bool


class Cmd2SimpleTable(Table):
    """A clean, lightweight Rich Table tailored for cmd2's internal use."""

    def __init__(self, *headers: Column | str) -> None:
        """Cmd2SimpleTable initializer."""
        super().__init__(
            *headers,
            box=SIMPLE_HEAD,
            show_edge=False,
            border_style=Cmd2Style.TABLE_BORDER,
        )


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
    :raises TypeError: if text is not a rich.text.Text object
    """
    # Strictly enforce Text type. While console.print() can render any object,
    # this function is specifically tailored to convert Text instances to strings.
    if not isinstance(text, Text):
        raise TypeError(f"rich_text_to_string() expected a rich.text.Text object, but got {type(text).__name__}")

    console = Console(
        force_terminal=True,
        color_system="truecolor",
        soft_wrap=True,
        no_color=False,
        theme=get_theme(),
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
