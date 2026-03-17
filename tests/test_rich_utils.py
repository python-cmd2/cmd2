"""Unit testing for cmd2/rich_utils.py module"""

import pytest
import rich.box
from pytest_mock import MockerFixture
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from cmd2 import (
    Cmd2Style,
    Color,
)
from cmd2 import rich_utils as ru


def test_cmd2_base_console() -> None:
    # Test the keyword arguments which are not allowed.
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
        (Text("Hello", style="blue"), "\x1b[34mHello\x1b[0m"),
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


def test_from_ansi_wrapper() -> None:
    # Check if we are still patching Text.from_ansi(). If this check fails, then Rich
    # has fixed the bug. Therefore, we can remove this test function and ru._from_ansi_wrapper.
    assert Text.from_ansi.__func__ is ru._from_ansi_wrapper.__func__  # type: ignore[attr-defined]

    # Line breaks recognized by str.splitlines().
    # Source: https://docs.python.org/3/library/stdtypes.html#str.splitlines
    line_breaks = {
        "\n",  # Line Feed
        "\r",  # Carriage Return
        "\r\n",  # Carriage Return + Line Feed
        "\v",  # Vertical Tab
        "\f",  # Form Feed
        "\x1c",  # File Separator
        "\x1d",  # Group Separator
        "\x1e",  # Record Separator
        "\x85",  # Next Line (NEL)
        "\u2028",  # Line Separator
        "\u2029",  # Paragraph Separator
    }

    # Test all line breaks
    for lb in line_breaks:
        input_string = f"Text{lb}"
        expected_output = input_string.replace(lb, "\n")
        assert Text.from_ansi(input_string).plain == expected_output

    # Test string without trailing line break
    input_string = "No trailing\nline break"
    assert Text.from_ansi(input_string).plain == input_string

    # Test empty string
    input_string = ""
    assert Text.from_ansi(input_string).plain == input_string


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
