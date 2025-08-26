"""Unit testing for cmd2/rich_utils.py module"""

import pytest
import rich.box
from rich.style import Style
from rich.table import Table
from rich.text import Text

from cmd2 import (
    Cmd2Style,
    Color,
)
from cmd2 import rich_utils as ru
from cmd2 import string_utils as su


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


def test_string_to_rich_text() -> None:
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
        assert ru.string_to_rich_text(input_string).plain == expected_output

    # Test string without trailing line break
    input_string = "No trailing\nline break"
    assert ru.string_to_rich_text(input_string).plain == input_string

    # Test empty string
    input_string = ""
    assert ru.string_to_rich_text(input_string).plain == input_string


def test_indented_text() -> None:
    console = ru.Cmd2GeneralConsole()

    # With an indention of 10, text will be evenly split across two lines.
    console.width = 20
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
    console = ru.Cmd2GeneralConsole()

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
        (Text("Hello", style="blue"), su.stylize("Hello", style="blue")),
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


def test_ansi_escape_sequence_re() -> None:
    import cmd2.terminal_utils as tu

    # Test a CSI sequence
    cursor_contol = tu.Cursor.UP(1)
    assert ru._ANSI_ESCAPE_SEQUENCE_RE.search(cursor_contol)

    # Test an OSC sequence
    set_title = tu.set_title_str("Hello")
    assert ru._ANSI_ESCAPE_SEQUENCE_RE.search(set_title)

    # Test DEC cursor save
    cursor_save = "\x1b\x37"
    assert ru._ANSI_ESCAPE_SEQUENCE_RE.search(cursor_save)

    # Test DEC cursor restore
    cursor_restore = "\x1b\x38"
    assert ru._ANSI_ESCAPE_SEQUENCE_RE.search(cursor_restore)
