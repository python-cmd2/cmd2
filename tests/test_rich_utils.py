"""Unit testing for cmd2/rich_utils.py module"""

import pytest
from rich.style import Style
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
