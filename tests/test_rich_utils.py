"""Unit testing for cmd2/rich_utils.py module"""

import pytest
import rich.box
from rich.console import Console
from rich.segment import Segment
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


@pytest.mark.parametrize(
    # Print with style and verify that everything but newline characters have style.
    ('objects', 'sep', 'end', 'expected'),
    [
        # Print nothing
        ((), " ", "\n", "\n"),
        # Empty string
        (("",), " ", "\n", "\n"),
        # Multple empty strings
        (("", ""), " ", "\n", "\x1b[34;47m \x1b[0m\n"),
        # Basic string
        (
            ("str_1",),
            " ",
            "\n",
            "\x1b[34;47mstr_1\x1b[0m\n",
        ),
        # String which ends with newline
        (
            ("str_1\n",),
            " ",
            "\n",
            "\x1b[34;47mstr_1\x1b[0m\n\n",
        ),
        # String which ends with multiple newlines
        (
            ("str_1\n\n",),
            " ",
            "\n",
            "\x1b[34;47mstr_1\x1b[0m\n\n\n",
        ),
        # Mutiple lines
        (
            ("str_1\nstr_2",),
            " ",
            "\n",
            "\x1b[34;47mstr_1\x1b[0m\n\x1b[34;47mstr_2\x1b[0m\n",
        ),
        # Multiple strings
        (
            ("str_1", "str_2"),
            " ",
            "\n",
            "\x1b[34;47mstr_1 str_2\x1b[0m\n",
        ),
        # Multiple strings with newline between them.
        (
            ("str_1\n", "str_2"),
            " ",
            "\n",
            "\x1b[34;47mstr_1\x1b[0m\n\x1b[34;47m str_2\x1b[0m\n",
        ),
        # Multiple strings and non-space value for sep
        (
            ("str_1", "str_2"),
            "(sep)",
            "\n",
            "\x1b[34;47mstr_1(sep)str_2\x1b[0m\n",
        ),
        # Multiple strings and sep is a newline
        (
            ("str_1", "str_2"),
            "\n",
            "\n",
            "\x1b[34;47mstr_1\x1b[0m\n\x1b[34;47mstr_2\x1b[0m\n",
        ),
        # Multiple strings and sep has newlines
        (
            ("str_1", "str_2"),
            "(sep1)\n(sep2)\n",
            "\n",
            ("\x1b[34;47mstr_1(sep1)\x1b[0m\n\x1b[34;47m(sep2)\x1b[0m\n\x1b[34;47mstr_2\x1b[0m\n"),
        ),
        # Non-newline value for end.
        (
            ("str_1", "str_2"),
            "(sep1)\n(sep2)",
            "(end)",
            "\x1b[34;47mstr_1(sep1)\x1b[0m\n\x1b[34;47m(sep2)str_2\x1b[0m\x1b[34;47m(end)\x1b[0m",
        ),
        # end has newlines.
        (
            ("str_1", "str_2"),
            "(sep1)\n(sep2)\n",
            "(end1)\n(end2)\n",
            (
                "\x1b[34;47mstr_1(sep1)\x1b[0m\n"
                "\x1b[34;47m(sep2)\x1b[0m\n"
                "\x1b[34;47mstr_2\x1b[0m\x1b[34;47m(end1)\x1b[0m\n"
                "\x1b[34;47m(end2)\x1b[0m\n"
            ),
        ),
        # Empty sep and end values
        (
            ("str_1", "str_2"),
            "",
            "",
            "\x1b[34;47mstr_1str_2\x1b[0m",
        ),
    ],
)
def test_apply_style_wrapper_soft_wrap(objects: tuple[str], sep: str, end: str, expected: str) -> None:
    # Check if we are still patching Segment.apply_style(). If this check fails, then Rich
    # has fixed the bug. Therefore, we can remove this test function and ru._apply_style_wrapper.
    assert Segment.apply_style.__func__ is ru._apply_style_wrapper.__func__  # type: ignore[attr-defined]

    console = Console(force_terminal=True)

    try:
        # Since our patch was meant to fix behavior seen when soft wrapping,
        # we will first test in that condition.
        with console.capture() as capture:
            console.print(*objects, sep=sep, end=end, style="blue on white", soft_wrap=True)
        result = capture.get()
        assert result == expected

        # Now print with soft wrapping disabled. Since none of our input strings are long enough
        # to auto wrap, the results should be the same as our soft-wrapping output.
        with console.capture() as capture:
            console.print(*objects, sep=sep, end=end, style="blue on white", soft_wrap=False)
        result = capture.get()
        assert result == expected

        # Now remove our patch and disable soft wrapping. This will prove that our patch produces
        # the same result as unpatched Rich
        Segment.apply_style = ru._orig_segment_apply_style  # type: ignore[assignment]

        with console.capture() as capture:
            console.print(*objects, sep=sep, end=end, style="blue on white", soft_wrap=False)
        result = capture.get()
        assert result == expected

    finally:
        # Restore the patch
        Segment.apply_style = ru._apply_style_wrapper  # type: ignore[assignment]


def test_apply_style_wrapper_word_wrap() -> None:
    """
    Test that our patch didn't mess up word wrapping.
    Make sure it does not insert styled newlines or apply style to existing newlines.
    """
    # Check if we are still patching Segment.apply_style(). If this check fails, then Rich
    # has fixed the bug. Therefore, we can remove this test function and ru._apply_style_wrapper.
    assert Segment.apply_style.__func__ is ru._apply_style_wrapper.__func__  # type: ignore[attr-defined]

    str1 = "this\nwill word wrap\n"
    str2 = "and\nso will this\n"
    sep = "(sep1)\n(sep2)\n"
    end = "(end1)\n(end2)\n"
    style = "blue on white"

    # All newlines should appear outside of ANSI style sequences.
    expected = (
        "\x1b[34;47mthis\x1b[0m\n"
        "\x1b[34;47mwill word \x1b[0m\n"
        "\x1b[34;47mwrap\x1b[0m\n"
        "\x1b[34;47m(sep1)\x1b[0m\n"
        "\x1b[34;47m(sep2)\x1b[0m\n"
        "\x1b[34;47mand\x1b[0m\n"
        "\x1b[34;47mso will \x1b[0m\n"
        "\x1b[34;47mthis\x1b[0m\n"
        "\x1b[34;47m(end1)\x1b[0m\n"
        "\x1b[34;47m(end2)\x1b[0m\n"
    )

    # Set a width which will cause word wrapping.
    console = Console(force_terminal=True, width=10)

    try:
        with console.capture() as capture:
            console.print(str1, str2, sep=sep, end=end, style=style, soft_wrap=False)
        assert capture.get() == expected

        # Now remove our patch and make sure it produced the same result as unpatched Rich.
        Segment.apply_style = ru._orig_segment_apply_style  # type: ignore[assignment]

        with console.capture() as capture:
            console.print(str1, str2, sep=sep, end=end, style=style, soft_wrap=False)
        assert capture.get() == expected

    finally:
        # Restore the patch
        Segment.apply_style = ru._apply_style_wrapper  # type: ignore[assignment]
