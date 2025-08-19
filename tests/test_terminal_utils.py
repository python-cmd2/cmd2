"""Unit testing for cmd2/terminal_utils.py module"""

import pytest

from cmd2 import (
    Color,
)
from cmd2 import string_utils as su
from cmd2 import terminal_utils as tu


def test_set_title() -> None:
    title = "Hello, world!"
    assert tu.set_title_str(title) == tu.OSC + '2;' + title + tu.BEL


@pytest.mark.parametrize(
    ('cols', 'prompt', 'line', 'cursor', 'msg', 'expected'),
    [
        (
            127,
            '(Cmd) ',
            'help his',
            12,
            su.stylize('Hello World!', style=Color.MAGENTA),
            '\x1b[2K\r\x1b[35mHello World!\x1b[0m',
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
    alert_str = tu.async_alert_str(terminal_columns=cols, prompt=prompt, line=line, cursor_offset=cursor, alert_msg=msg)
    assert alert_str == expected


def test_clear_screen() -> None:
    clear_type = 2
    assert tu.clear_screen_str(clear_type) == f"{tu.CSI}{clear_type}J"

    clear_type = -1
    expected_err = "clear_type must in an integer from 0 to 3"
    with pytest.raises(ValueError, match=expected_err):
        tu.clear_screen_str(clear_type)

    clear_type = 4
    with pytest.raises(ValueError, match=expected_err):
        tu.clear_screen_str(clear_type)


def test_clear_line() -> None:
    clear_type = 2
    assert tu.clear_line_str(clear_type) == f"{tu.CSI}{clear_type}K"

    clear_type = -1
    expected_err = "clear_type must in an integer from 0 to 2"
    with pytest.raises(ValueError, match=expected_err):
        tu.clear_line_str(clear_type)

    clear_type = 3
    with pytest.raises(ValueError, match=expected_err):
        tu.clear_line_str(clear_type)


def test_cursor() -> None:
    count = 1
    assert tu.Cursor.UP(count) == f"{tu.CSI}{count}A"
    assert tu.Cursor.DOWN(count) == f"{tu.CSI}{count}B"
    assert tu.Cursor.FORWARD(count) == f"{tu.CSI}{count}C"
    assert tu.Cursor.BACK(count) == f"{tu.CSI}{count}D"

    x = 4
    y = 5
    assert tu.Cursor.SET_POS(x, y) == f"{tu.CSI}{y};{x}H"
