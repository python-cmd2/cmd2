"""Unit testing for cmd2/rich_utils.py module"""

import sys
from typing import Any
from unittest import mock

import pytest
import rich.box
from pytest_mock import MockerFixture
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from cmd2 import (
    Cmd2ArgumentParser,
    Cmd2Style,
    Color,
)
from cmd2 import rich_utils as ru

from .conftest import with_ansi_style


def test_cmd2_base_console() -> None:
    # Test the keyword arguments which are not allowed.
    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(color_system="auto")
    assert "color_system" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(force_terminal=True)
    assert "force_terminal" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(force_interactive=True)
    assert "force_interactive" in str(excinfo.value)

    with pytest.raises(TypeError) as excinfo:
        ru.Cmd2BaseConsole(theme=None)
    assert "theme" in str(excinfo.value)


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
    ("rich_text", "string"),
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


def test_rich_text_to_string_type_error() -> None:
    with pytest.raises(TypeError) as excinfo:
        ru.rich_text_to_string("not a Text object")  # type: ignore[arg-type]
    assert "rich_text_to_string() expected a rich.text.Text object, but got str" in str(excinfo.value)


def test_set_theme() -> None:
    # Save a cmd2, rich-argparse, and rich-specific style.
    cmd2_style_key = Cmd2Style.ERROR
    argparse_style_key = "argparse.args"
    rich_style_key = "inspect.attr"

    theme = ru.get_theme()
    orig_cmd2_style = theme.styles[cmd2_style_key]
    orig_argparse_style = theme.styles[argparse_style_key]
    orig_rich_style = theme.styles[rich_style_key]

    # Overwrite these styles by setting a new theme.
    new_styles = {
        cmd2_style_key: Style(color=Color.CYAN),
        argparse_style_key: Style(color=Color.AQUAMARINE3, underline=True),
        rich_style_key: Style(color=Color.DARK_GOLDENROD, bold=True),
    }
    ru.set_theme(new_styles)

    # Verify theme styles have changed to our custom values.
    assert theme.styles[cmd2_style_key] != orig_cmd2_style
    assert theme.styles[cmd2_style_key] == new_styles[cmd2_style_key]

    assert theme.styles[argparse_style_key] != orig_argparse_style
    assert theme.styles[argparse_style_key] == new_styles[argparse_style_key]

    assert theme.styles[rich_style_key] != orig_rich_style
    assert theme.styles[rich_style_key] == new_styles[rich_style_key]


def test_cmd2_base_console_print(mocker: MockerFixture) -> None:
    """Test that Cmd2BaseConsole.print() calls prepare_objects_for_rendering()."""
    # Mock prepare_objects_for_rendering to return a specific value
    prepared_val = ("prepared",)
    mock_prepare = mocker.patch("cmd2.rich_utils.prepare_objects_for_rendering", return_value=prepared_val)

    # Mock the superclass print() method
    mock_super_print = mocker.patch("rich.console.Console.print")

    console = ru.Cmd2BaseConsole()
    console.print("hello")

    # Verify that prepare_objects_for_rendering() was called with the input objects
    mock_prepare.assert_called_once_with("hello")

    # Verify that the superclass print() method was called with the prepared objects
    args, _ = mock_super_print.call_args
    assert args == prepared_val


def test_cmd2_base_console_log(mocker: MockerFixture) -> None:
    """Test that Cmd2BaseConsole.log() calls prepare_objects_for_rendering() and increments _stack_offset."""
    # Mock prepare_objects_for_rendering to return a specific value
    prepared_val = ("prepared",)
    mock_prepare = mocker.patch("cmd2.rich_utils.prepare_objects_for_rendering", return_value=prepared_val)

    # Mock the superclass log() method
    mock_super_log = mocker.patch("rich.console.Console.log")

    console = ru.Cmd2BaseConsole()
    console.log("test", _stack_offset=2)

    # Verify that prepare_objects_for_rendering() was called with the input objects
    mock_prepare.assert_called_once_with("test")

    # Verify that the superclass log() method was called with the prepared objects
    # and that the stack offset was correctly incremented.
    args, kwargs = mock_super_log.call_args
    assert args == prepared_val
    assert kwargs["_stack_offset"] == 3


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_cmd2_base_console_init_always_interactive_true() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is ALWAYS and is_interactive is True."""
    with (
        mock.patch("rich.console.Console.__init__", return_value=None) as mock_base_init,
        mock.patch("cmd2.rich_utils.Console", autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_interactive = True

        ru.Cmd2BaseConsole()

        # Verify arguments passed to super().__init__
        _, kwargs = mock_base_init.call_args
        assert kwargs["color_system"] == "truecolor"
        assert kwargs["force_terminal"] is True
        assert kwargs["force_interactive"] is True


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_cmd2_base_console_init_always_interactive_false() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is ALWAYS and is_interactive is False."""
    with (
        mock.patch("rich.console.Console.__init__", return_value=None) as mock_base_init,
        mock.patch("cmd2.rich_utils.Console", autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_interactive = False

        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs["color_system"] == "truecolor"
        assert kwargs["force_terminal"] is True
        assert kwargs["force_interactive"] is False


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_cmd2_base_console_init_terminal_true() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is TERMINAL and it is a terminal."""
    with (
        mock.patch("rich.console.Console.__init__", return_value=None) as mock_base_init,
        mock.patch("cmd2.rich_utils.Console", autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_terminal = True

        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs["color_system"] == "truecolor"
        assert kwargs["force_terminal"] is None
        assert kwargs["force_interactive"] is None


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_cmd2_base_console_init_terminal_false() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is TERMINAL and it is not a terminal."""
    with (
        mock.patch("rich.console.Console.__init__", return_value=None) as mock_base_init,
        mock.patch("cmd2.rich_utils.Console", autospec=True) as mock_detect_console_class,
    ):
        mock_detect_console = mock_detect_console_class.return_value
        mock_detect_console.is_terminal = False

        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs["color_system"] is None
        assert kwargs["force_terminal"] is None
        assert kwargs["force_interactive"] is None


@with_ansi_style(ru.AllowStyle.NEVER)
def test_cmd2_base_console_init_never() -> None:
    """Test Cmd2BaseConsole initialization when ALLOW_STYLE is NEVER."""
    with mock.patch("rich.console.Console.__init__", return_value=None) as mock_base_init:
        ru.Cmd2BaseConsole()

        _, kwargs = mock_base_init.call_args
        assert kwargs["color_system"] is None
        assert kwargs["force_terminal"] is False
        assert kwargs["force_interactive"] is None


def test_text_group_in_parser(capsys: pytest.CaptureFixture[str]) -> None:
    """Print a TextGroup with argparse."""
    parser = Cmd2ArgumentParser(prog="test")
    parser.epilog = ru.TextGroup("Notes", "Some text")

    # Render help
    parser.print_help()
    out, _ = capsys.readouterr()

    assert "Notes:" in out
    assert "  Some text" in out


def test_formatter_console() -> None:
    # self._console = console (inside console.setter)
    formatter = ru.Cmd2HelpFormatter(prog="test")
    new_console = ru.Cmd2RichArgparseConsole()
    formatter.console = new_console
    assert formatter._console is new_console


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Argparse didn't support color until Python 3.14",
)
def test_formatter_set_color(mocker: MockerFixture) -> None:
    formatter = ru.Cmd2HelpFormatter(prog="test")

    # return (inside _set_color if sys.version_info < (3, 14))
    mocker.patch("cmd2.argparse_utils.sys.version_info", (3, 13, 0))
    # This should return early without calling super()._set_color
    mock_set_color = mocker.patch("rich_argparse.RichHelpFormatter._set_color")
    formatter._set_color(True)
    mock_set_color.assert_not_called()

    # except TypeError and super()._set_color(color)
    mocker.patch("cmd2.argparse_utils.sys.version_info", (3, 15, 0))

    # Reset mock and make it raise TypeError when called with kwargs
    mock_set_color.reset_mock()

    def side_effect(color: bool, **kwargs: Any) -> None:
        if kwargs:
            raise TypeError("unexpected keyword argument 'file'")
        return

    mock_set_color.side_effect = side_effect

    # This call should trigger the TypeError and then the fallback call
    formatter._set_color(True, file=sys.stdout)

    # It should have been called twice: once with kwargs (failed) and once without (fallback)
    assert mock_set_color.call_count == 2
    mock_set_color.assert_any_call(True, file=sys.stdout)
    mock_set_color.assert_any_call(True)
