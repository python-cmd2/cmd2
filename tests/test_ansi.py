"""Unit testing for cmd2/ansi.py module"""

import pytest

from cmd2 import (
    ansi,
    string_utils,
)

HELLO_WORLD = 'Hello, world!'


def test_set_title() -> None:
    title = HELLO_WORLD
    assert ansi.set_title_str(title) == ansi.OSC + '2;' + title + ansi.BEL


@pytest.mark.parametrize(
    ('cols', 'prompt', 'line', 'cursor', 'msg', 'expected'),
    [
        (
            127,
            '(Cmd) ',
            'help his',
            12,
            string_utils.style('Hello World!', style="magenta"),
            '\x1b[2K\r\x1b[35mHello World!\x1b[39m',
        ),
        (127, '\n(Cmd) ', 'help ', 5, 'foo', '\x1b[2K\x1b[1A\x1b[2K\rfoo'),
        (
            10,
            '(Cmd) ',
            'help history of the american republic',
            4,
            'boo',
            '\x1b[3B\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K\rboo',
        ),
    ],
)
def test_async_alert_str(cols, prompt, line, cursor, msg, expected) -> None:
    alert_str = ansi.async_alert_str(terminal_columns=cols, prompt=prompt, line=line, cursor_offset=cursor, alert_msg=msg)
    assert alert_str == expected


def test_clear_screen() -> None:
    clear_type = 2
    assert ansi.clear_screen_str(clear_type) == f"{ansi.CSI}{clear_type}J"

    clear_type = -1
    expected_err = "clear_type must in an integer from 0 to 3"
    with pytest.raises(ValueError, match=expected_err):
        ansi.clear_screen_str(clear_type)

    clear_type = 4
    with pytest.raises(ValueError, match=expected_err):
        ansi.clear_screen_str(clear_type)


def test_clear_line() -> None:
    clear_type = 2
    assert ansi.clear_line_str(clear_type) == f"{ansi.CSI}{clear_type}K"

    clear_type = -1
    expected_err = "clear_type must in an integer from 0 to 2"
    with pytest.raises(ValueError, match=expected_err):
        ansi.clear_line_str(clear_type)

    clear_type = 3
    with pytest.raises(ValueError, match=expected_err):
        ansi.clear_line_str(clear_type)


def test_cursor() -> None:
    count = 1
    assert ansi.Cursor.UP(count) == f"{ansi.CSI}{count}A"
    assert ansi.Cursor.DOWN(count) == f"{ansi.CSI}{count}B"
    assert ansi.Cursor.FORWARD(count) == f"{ansi.CSI}{count}C"
    assert ansi.Cursor.BACK(count) == f"{ansi.CSI}{count}D"

    x = 4
    y = 5
    assert ansi.Cursor.SET_POS(x, y) == f"{ansi.CSI}{y};{x}H"
