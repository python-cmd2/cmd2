# coding=utf-8
# flake8: noqa E302
"""
Unit testing for cmd2/ansi.py module
"""

import pytest

from cmd2 import (
    ansi,
)

HELLO_WORLD = 'Hello, world!'


def test_strip_style():
    base_str = HELLO_WORLD
    ansi_str = ansi.style(base_str, fg=ansi.Fg.GREEN)
    assert base_str != ansi_str
    assert base_str == ansi.strip_style(ansi_str)


def test_style_aware_wcswidth():
    base_str = HELLO_WORLD
    ansi_str = ansi.style(base_str, fg=ansi.Fg.GREEN)
    assert ansi.style_aware_wcswidth(HELLO_WORLD) == ansi.style_aware_wcswidth(ansi_str)

    assert ansi.style_aware_wcswidth('i have a tab\t') == -1
    assert ansi.style_aware_wcswidth('i have a newline\n') == -1


def test_widest_line():
    text = ansi.style('i have\n3 lines\nThis is the longest one', fg=ansi.Fg.GREEN)
    assert ansi.widest_line(text) == ansi.style_aware_wcswidth("This is the longest one")

    text = "I'm just one line"
    assert ansi.widest_line(text) == ansi.style_aware_wcswidth(text)

    assert ansi.widest_line('i have a tab\t') == -1


def test_style_none():
    base_str = HELLO_WORLD
    ansi_str = base_str
    assert ansi.style(base_str) == ansi_str


@pytest.mark.parametrize('fg_color', [ansi.Fg.BLUE, ansi.EightBitFg.AQUAMARINE_1A, ansi.RgbFg(0, 2, 4)])
def test_style_fg(fg_color):
    base_str = HELLO_WORLD
    ansi_str = fg_color + base_str + ansi.Fg.RESET
    assert ansi.style(base_str, fg=fg_color) == ansi_str


@pytest.mark.parametrize('bg_color', [ansi.Bg.BLUE, ansi.EightBitBg.AQUAMARINE_1A, ansi.RgbBg(0, 2, 4)])
def test_style_bg(bg_color):
    base_str = HELLO_WORLD
    ansi_str = bg_color + base_str + ansi.Bg.RESET
    assert ansi.style(base_str, bg=bg_color) == ansi_str


def test_style_invalid_types():
    # Use a BgColor with fg
    with pytest.raises(TypeError):
        ansi.style('test', fg=ansi.Bg.BLUE)

    # Use a FgColor with bg
    with pytest.raises(TypeError):
        ansi.style('test', bg=ansi.Fg.BLUE)


def test_style_bold():
    base_str = HELLO_WORLD
    ansi_str = ansi.TextStyle.INTENSITY_BOLD + base_str + ansi.TextStyle.INTENSITY_NORMAL
    assert ansi.style(base_str, bold=True) == ansi_str


def test_style_dim():
    base_str = HELLO_WORLD
    ansi_str = ansi.TextStyle.INTENSITY_DIM + base_str + ansi.TextStyle.INTENSITY_NORMAL
    assert ansi.style(base_str, dim=True) == ansi_str


def test_style_italic():
    base_str = HELLO_WORLD
    ansi_str = ansi.TextStyle.ITALIC_ENABLE + base_str + ansi.TextStyle.ITALIC_DISABLE
    assert ansi.style(base_str, italic=True) == ansi_str


def test_style_overline():
    base_str = HELLO_WORLD
    ansi_str = ansi.TextStyle.OVERLINE_ENABLE + base_str + ansi.TextStyle.OVERLINE_DISABLE
    assert ansi.style(base_str, overline=True) == ansi_str


def test_style_strikethrough():
    base_str = HELLO_WORLD
    ansi_str = ansi.TextStyle.STRIKETHROUGH_ENABLE + base_str + ansi.TextStyle.STRIKETHROUGH_DISABLE
    assert ansi.style(base_str, strikethrough=True) == ansi_str


def test_style_underline():
    base_str = HELLO_WORLD
    ansi_str = ansi.TextStyle.UNDERLINE_ENABLE + base_str + ansi.TextStyle.UNDERLINE_DISABLE
    assert ansi.style(base_str, underline=True) == ansi_str


def test_style_multi():
    base_str = HELLO_WORLD
    fg_color = ansi.Fg.LIGHT_BLUE
    bg_color = ansi.Bg.LIGHT_GRAY
    ansi_str = (
        fg_color
        + bg_color
        + ansi.TextStyle.INTENSITY_BOLD
        + ansi.TextStyle.INTENSITY_DIM
        + ansi.TextStyle.ITALIC_ENABLE
        + ansi.TextStyle.OVERLINE_ENABLE
        + ansi.TextStyle.STRIKETHROUGH_ENABLE
        + ansi.TextStyle.UNDERLINE_ENABLE
        + base_str
        + ansi.Fg.RESET
        + ansi.Bg.RESET
        + ansi.TextStyle.INTENSITY_NORMAL
        + ansi.TextStyle.INTENSITY_NORMAL
        + ansi.TextStyle.ITALIC_DISABLE
        + ansi.TextStyle.OVERLINE_DISABLE
        + ansi.TextStyle.STRIKETHROUGH_DISABLE
        + ansi.TextStyle.UNDERLINE_DISABLE
    )
    assert (
        ansi.style(
            base_str,
            fg=fg_color,
            bg=bg_color,
            bold=True,
            dim=True,
            italic=True,
            overline=True,
            strikethrough=True,
            underline=True,
        )
        == ansi_str
    )


def test_set_title():
    title = HELLO_WORLD
    assert ansi.set_title(title) == ansi.OSC + '2;' + title + ansi.BEL


@pytest.mark.parametrize(
    'cols, prompt, line, cursor, msg, expected',
    [
        (
            127,
            '(Cmd) ',
            'help his',
            12,
            ansi.style('Hello World!', fg=ansi.Fg.MAGENTA),
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
def test_async_alert_str(cols, prompt, line, cursor, msg, expected):
    alert_str = ansi.async_alert_str(terminal_columns=cols, prompt=prompt, line=line, cursor_offset=cursor, alert_msg=msg)
    assert alert_str == expected


def test_clear_screen():
    clear_type = 2
    assert ansi.clear_screen(clear_type) == f"{ansi.CSI}{clear_type}J"

    clear_type = -1
    with pytest.raises(ValueError):
        ansi.clear_screen(clear_type)

    clear_type = 4
    with pytest.raises(ValueError):
        ansi.clear_screen(clear_type)


def test_clear_line():
    clear_type = 2
    assert ansi.clear_line(clear_type) == f"{ansi.CSI}{clear_type}K"

    clear_type = -1
    with pytest.raises(ValueError):
        ansi.clear_line(clear_type)

    clear_type = 3
    with pytest.raises(ValueError):
        ansi.clear_line(clear_type)


def test_cursor():
    count = 1
    assert ansi.Cursor.UP(count) == f"{ansi.CSI}{count}A"
    assert ansi.Cursor.DOWN(count) == f"{ansi.CSI}{count}B"
    assert ansi.Cursor.FORWARD(count) == f"{ansi.CSI}{count}C"
    assert ansi.Cursor.BACK(count) == f"{ansi.CSI}{count}D"

    x = 4
    y = 5
    assert ansi.Cursor.SET_POS(x, y) == f"{ansi.CSI}{y};{x}H"


@pytest.mark.parametrize(
    'ansi_sequence',
    [
        ansi.Fg.MAGENTA,
        ansi.Bg.LIGHT_GRAY,
        ansi.EightBitBg.CHARTREUSE_2A,
        ansi.EightBitBg.MEDIUM_PURPLE,
        ansi.RgbFg(0, 5, 22),
        ansi.RgbBg(100, 150, 222),
        ansi.TextStyle.OVERLINE_ENABLE,
    ],
)
def test_sequence_str_building(ansi_sequence):
    """This tests __add__(), __radd__(), and __str__() methods for AnsiSequences"""
    assert ansi_sequence + ansi_sequence == str(ansi_sequence) + str(ansi_sequence)


@pytest.mark.parametrize(
    'r, g, b, valid',
    [
        (0, 0, 0, True),
        (255, 255, 255, True),
        (-1, 0, 0, False),
        (256, 255, 255, False),
        (0, -1, 0, False),
        (255, 256, 255, False),
        (0, 0, -1, False),
        (255, 255, 256, False),
    ],
)
def test_rgb_bounds(r, g, b, valid):
    if valid:
        ansi.RgbFg(r, g, b)
        ansi.RgbBg(r, g, b)
    else:
        with pytest.raises(ValueError):
            ansi.RgbFg(r, g, b)
        with pytest.raises(ValueError):
            ansi.RgbBg(r, g, b)


def test_std_color_re():
    """Test regular expressions for matching standard foreground and background colors"""
    for color in ansi.Fg:
        assert ansi.STD_FG_RE.match(str(color))
        assert not ansi.STD_BG_RE.match(str(color))
    for color in ansi.Bg:
        assert ansi.STD_BG_RE.match(str(color))
        assert not ansi.STD_FG_RE.match(str(color))

    # Test an invalid color code
    assert not ansi.STD_FG_RE.match(f'{ansi.CSI}38m')
    assert not ansi.STD_BG_RE.match(f'{ansi.CSI}48m')


def test_eight_bit_color_re():
    """Test regular expressions for matching eight-bit foreground and background colors"""
    for color in ansi.EightBitFg:
        assert ansi.EIGHT_BIT_FG_RE.match(str(color))
        assert not ansi.EIGHT_BIT_BG_RE.match(str(color))
    for color in ansi.EightBitBg:
        assert ansi.EIGHT_BIT_BG_RE.match(str(color))
        assert not ansi.EIGHT_BIT_FG_RE.match(str(color))

    # Test invalid eight-bit value (256)
    assert not ansi.EIGHT_BIT_FG_RE.match(f'{ansi.CSI}38;5;256m')
    assert not ansi.EIGHT_BIT_BG_RE.match(f'{ansi.CSI}48;5;256m')


def test_rgb_color_re():
    """Test regular expressions for matching RGB foreground and background colors"""
    for i in range(256):
        fg_color = ansi.RgbFg(i, i, i)
        assert ansi.RGB_FG_RE.match(str(fg_color))
        assert not ansi.RGB_BG_RE.match(str(fg_color))

        bg_color = ansi.RgbBg(i, i, i)
        assert ansi.RGB_BG_RE.match(str(bg_color))
        assert not ansi.RGB_FG_RE.match(str(bg_color))

    # Test invalid RGB value (256)
    assert not ansi.RGB_FG_RE.match(f'{ansi.CSI}38;2;256;256;256m')
    assert not ansi.RGB_BG_RE.match(f'{ansi.CSI}48;2;256;256;256m')
