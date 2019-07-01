# coding=utf-8
# flake8: noqa E302
"""
Unit testing for cmd2/ansi.py module
"""
import pytest

import cmd2.ansi as ansi

HELLO_WORLD = 'Hello, world!'


def test_strip_ansi():
    base_str = HELLO_WORLD
    ansi_str = ansi.style(base_str, fg='green')
    assert base_str != ansi_str
    assert base_str == ansi.strip_ansi(ansi_str)


def test_ansi_safe_wcswidth():
    base_str = HELLO_WORLD
    ansi_str = ansi.style(base_str, fg='green')
    assert ansi.ansi_safe_wcswidth(ansi_str) != len(ansi_str)


def test_style_none():
    base_str = HELLO_WORLD
    ansi_str = base_str
    assert ansi.style(base_str) == ansi_str


def test_style_fg():
    base_str = HELLO_WORLD
    fg_color = 'blue'
    ansi_str = ansi.FG_COLORS[fg_color] + base_str + ansi.FG_RESET
    assert ansi.style(base_str, fg=fg_color) == ansi_str


def test_style_bg():
    base_str = HELLO_WORLD
    bg_color = 'green'
    ansi_str = ansi.BG_COLORS[bg_color] + base_str + ansi.BG_RESET
    assert ansi.style(base_str, bg=bg_color) == ansi_str


def test_style_bold():
    base_str = HELLO_WORLD
    ansi_str = ansi.BRIGHT + base_str + ansi.NORMAL
    assert ansi.style(base_str, bold=True) == ansi_str


def test_style_underline():
    base_str = HELLO_WORLD
    ansi_str = ansi.UNDERLINE_ENABLE + base_str + ansi.UNDERLINE_DISABLE
    assert ansi.style(base_str, underline=True) == ansi_str


def test_style_multi():
    base_str = HELLO_WORLD
    fg_color = 'blue'
    bg_color = 'green'
    ansi_str = ansi.FG_COLORS[fg_color] + ansi.BG_COLORS[bg_color] + ansi.BRIGHT + ansi.UNDERLINE_ENABLE + \
               base_str + ansi.FG_RESET + ansi.BG_RESET + ansi.NORMAL + ansi.UNDERLINE_DISABLE
    assert ansi.style(base_str, fg=fg_color, bg=bg_color, bold=True, underline=True) == ansi_str


def test_style_color_not_exist():
    base_str = HELLO_WORLD

    with pytest.raises(ValueError):
        ansi.style(base_str, fg='fake', bg='green')

    with pytest.raises(ValueError):
        ansi.style(base_str, fg='blue', bg='fake')


def test_fg_lookup_exist():
    fg_color = 'green'
    assert ansi.fg_lookup(fg_color) == ansi.FG_COLORS[fg_color]


def test_fg_lookup_nonexist():
    with pytest.raises(ValueError):
        ansi.fg_lookup('foo')


def test_bg_lookup_exist():
    bg_color = 'green'
    assert ansi.bg_lookup(bg_color) == ansi.BG_COLORS[bg_color]


def test_bg_lookup_nonexist():
    with pytest.raises(ValueError):
        ansi.bg_lookup('bar')


def test_set_title_str():
    OSC = '\033]'
    BEL = '\007'
    title = HELLO_WORLD
    assert ansi.set_title_str(title) == OSC + '2;' + title + BEL


@pytest.mark.parametrize('cols, prompt, line, cursor, msg, expected', [
    (127, '(Cmd) ', 'help his', 12, ansi.style('Hello World!', fg='magenta'), '\x1b[2K\r\x1b[35mHello World!\x1b[39m'),
    (127, '\n(Cmd) ', 'help ', 5, 'foo', '\x1b[2K\x1b[1A\x1b[2K\rfoo'),
    (10, '(Cmd) ', 'help history of the american republic', 4, 'boo', '\x1b[3B\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K\rboo')
])
def test_async_alert_str(cols, prompt, line, cursor, msg, expected):
    alert_str = ansi.async_alert_str(terminal_columns=cols, prompt=prompt, line=line, cursor_offset=cursor,
                                     alert_msg=msg)
    assert alert_str == expected
