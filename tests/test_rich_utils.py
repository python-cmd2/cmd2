"""Unit testing for cmd2/rich_utils.py module"""

from unittest import mock

import pytest
import rich.box
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from cmd2 import (
    Cmd2Style,
    Color,
)
from cmd2 import rich_utils as ru

from .conftest import with_ansi_style


def test_cmd2_base_console() -> None:
    # Test the keyword arguments which are not allowed.
    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(color_system="auto")
    assert 'color_system' in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(force_terminal=True)
    assert 'force_terminal' in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(force_interactive=True)
    assert 'force_interactive' in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(theme=None)
    assert 'theme' in str(excinfo.value)


def test_indented_text() -> None:
    console = Console(width=20)

    # With an indention of 10, text will be evenly split across two lines.
    text = "A" * 20
    level = 10
    indented_text = ru.indent(text, level)

    with console.capture() as capture:
        console.print(indented_text)
    result = capture.get().splitlines()

    padding = " " * level
    expected_line = padding + ("A" * 10)
    assert result[0] == expected_line
    assert result[1] == expected_line


def test_indented_table() -> None:
    console = Console()

    level = 2
    table = Table("Column", box=rich.box.ASCII)
    table.add_row("Some Data")
    indented_table = ru.indent(table, level)

    with console.capture() as capture:
        console.print(indented_table)
    result = capture.get().splitlines()

    padding = " " * level
    assert result[0].startswith(padding + "+-----------+")
    assert result[1].startswith(padding + "| Column    |")
    assert result[2].startswith(padding + "|-----------|")
    assert result[3].startswith(padding + "| Some Data |")
    assert result[4].startswith(padding + "+-----------+")


@pytest.mark.parametrize(
    ('rich_text', 'string'),
    [
        (Text("Hello"), "Hello"),
        (Text("Hello\n"), "Hello\n"),
        # Test standard color support
        (Text("Standard", style="blue"), "\x1b[34mStandard\x1b[0m"),
        # Test 256-color support
        (Text("256-color", style=Color.NAVY_BLUE), "\x1b[38;5;17m256-color\x1b[0m"),
        # Test 24-bit color (TrueColor) support
        (Text("TrueColor", style="#123456"), "\x1b[38;2;18;52;86mTrueColor\x1b[0m"),
    ],
)
def test_rich_text_to_string(rich_text: Text, string: str) -> None:
    assert ru.rich_text_to_string(rich_text) == string


def test_set_theme() -> None:
    # Save a cmd2, rich-argparse, and rich-specific style.
    cmd2_style_key = Cmd2Style.ERROR
    argparse_style_key = "argparse.args"
    rich_style_key = "inspect.attr"

    orig_cmd2_style = ru.APP_THEME.styles[cmd2_style_key]
    orig_argparse_style = ru.APP_THEME.styles[argparse_style_key]
    orig_rich_style = ru.APP_THEME.styles[rich_style_key]

    # Overwrite these styles by setting a new theme.
    theme = {
        cmd2_style_key: Style(color=Color.CYAN),
        argparse_style_key: Style(color=Color.AQUAMARINE3, underline=True),
        rich_style_key: Style(color=Color.DARK_GOLDENROD, bold=True),
    }
    ru.set_theme(theme)

    # Verify theme styles have changed to our custom values.
    assert ru.APP_THEME.styles[cmd2_style_key] != orig_cmd2_style
    assert ru.APP_THEME.styles[cmd2_style_key] == theme[cmd2_style_key]

    assert ru.APP_THEME.styles[argparse_style_key] != orig_argparse_style
    assert ru.APP_THEME.styles[argparse_style_key] == theme[argparse_style_key]

    assert ru.APP_THEME.styles[rich_style_key] != orig_rich_style
    assert ru.APP_THEME.styles[rich_style_key] == theme[rich_style_key]


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_cmd2_base_console_print() -> None:
    """Test that Cmd2BaseConsole.print() correctly propagates formatting overrides to structured renderables."""
    from rich.rule import Rule

    # Create a console that defaults to no formatting
    console = ru.Cmd2BaseConsole(emoji=False, markup=False)

    # Use a Rule with emoji and markup in the title
    rule = Rule(title="[green]Success :1234:[/green]")

    with console.capture() as capture:
        # Override settings in the print() call
        console.print(rule, emoji=True, markup=True)

    result = capture.get()

    # Verify that the overrides were respected by checking for the emoji and the color code
    assert "🔢" in result
    assert "\x1b[32mSuccess" in result


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_cmd2_base_console_log() -> None:
    """Test that Cmd2BaseConsole.log() correctly propagates formatting overrides to structured renderables."""
    from rich.rule import Rule

    # Create a console that defaults to no formatting
    console = ru.Cmd2BaseConsole(emoji=False, markup=False)

    # Use a Rule with emoji and markup in the title
    rule = Rule(title="[green]Success :1234:[/green]")

    with console.capture() as capture:
        # Override settings in the log() call
        console.log(rule, emoji=True, markup=True)

    result = capture.get()

    # Verify that the formatting overrides were respected
    assert "🔢" in result
    assert "\x1b[32mSuccess" in result

    # Verify stack offset: the log line should point to this file, not rich_utils.py
    # Rich logs include the filename and line number on the right.
    assert "test_rich_utils.py" in result


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_cmd2_base_console_init_always_interactive_true() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is ALWAYS and is_interactive is True."""
    with (
        mock.patch('rich.console.Console.__init__', return_value=None) as mock_base_init,
        mock.patch('cmd2.rich_utils.Console', autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_interactive = True

        ru.Cmd2BaseConsole()

        # Verify arguments passed to super().__init__
        _, kwargs = mock_base_init.call_args
        assert kwargs['color_system'] == "truecolor"
        assert kwargs['force_terminal'] is True
        assert kwargs['force_interactive'] is True


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_cmd2_base_console_init_always_interactive_false() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is ALWAYS and is_interactive is False."""
    with (
        mock.patch('rich.console.Console.__init__', return_value=None) as mock_base_init,
        mock.patch('cmd2.rich_utils.Console', autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_interactive = False

        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs['color_system'] == "truecolor"
        assert kwargs['force_terminal'] is True
        assert kwargs['force_interactive'] is False


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_cmd2_base_console_init_terminal_true() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is TERMINAL and it is a terminal."""
    with (
        mock.patch('rich.console.Console.__init__', return_value=None) as mock_base_init,
        mock.patch('cmd2.rich_utils.Console', autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_terminal = True

        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs['color_system'] == "truecolor"
        assert kwargs['force_terminal'] is None
        assert kwargs['force_interactive'] is None


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_cmd2_base_console_init_terminal_false() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is TERMINAL and it is not a terminal."""
    with (
        mock.patch('rich.console.Console.__init__', return_value=None) as mock_base_init,
        mock.patch('cmd2.rich_utils.Console', autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_terminal = False

        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs['color_system'] is None
        assert kwargs['force_terminal'] is None
        assert kwargs['force_interactive'] is None


@with_ansi_style(ru.AllowStyle.NEVER)
def test_cmd2_base_console_init_never() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is NEVER."""
    with mock.patch('rich.console.Console.__init__', return_value=None) as mock_base_init:
        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs['color_system'] is None
        assert kwargs['force_terminal'] is False
        assert kwargs['force_interactive'] is None
