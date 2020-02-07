# coding=utf-8
# flake8: noqa E302
"""
Unit testing for cmd2/ansi.py module
"""
import pytest

import cmd2.ansi as ansi

HELLO_WORLD = 'Hello, world!'


def test_strip_style():
    base_str = HELLO_WORLD
    ansi_str = ansi.style(base_str, fg='green')
    assert base_str != ansi_str
    assert base_str == ansi.strip_style(ansi_str)


def test_style_aware_wcswidth():
    base_str = HELLO_WORLD
    ansi_str = ansi.style(base_str, fg='green')
    assert ansi.style_aware_wcswidth(ansi_str) != len(ansi_str)


def test_style_none():
    base_str = HELLO_WORLD
    ansi_str = base_str
    assert ansi.style(base_str) == ansi_str


def test_style_fg():
    base_str = HELLO_WORLD
    fg_color = 'blue'
    ansi_str = ansi.fg[fg_color].value + base_str + ansi.FG_RESET
    assert ansi.style(base_str, fg=fg_color) == ansi_str


def test_style_bg():
    base_str = HELLO_WORLD
    bg_color = 'green'
    ansi_str = ansi.bg[bg_color].value + base_str + ansi.BG_RESET
    assert ansi.style(base_str, bg=bg_color) == ansi_str


def test_style_bold():
    base_str = HELLO_WORLD
    ansi_str = ansi.INTENSITY_BRIGHT + base_str + ansi.INTENSITY_NORMAL
    assert ansi.style(base_str, bold=True) == ansi_str


def test_style_dim():
    base_str = HELLO_WORLD
    ansi_str = ansi.INTENSITY_DIM + base_str + ansi.INTENSITY_NORMAL
    assert ansi.style(base_str, dim=True) == ansi_str


def test_style_underline():
    base_str = HELLO_WORLD
    ansi_str = ansi.UNDERLINE_ENABLE + base_str + ansi.UNDERLINE_DISABLE
    assert ansi.style(base_str, underline=True) == ansi_str


def test_style_multi():
    base_str = HELLO_WORLD
    fg_color = 'blue'
    bg_color = 'green'
    ansi_str = (ansi.fg[fg_color].value + ansi.bg[bg_color].value +
                ansi.INTENSITY_BRIGHT + ansi.INTENSITY_DIM + ansi.UNDERLINE_ENABLE +
                base_str +
                ansi.FG_RESET + ansi.BG_RESET +
                ansi.INTENSITY_NORMAL + ansi.INTENSITY_NORMAL + ansi.UNDERLINE_DISABLE)
    assert ansi.style(base_str, fg=fg_color, bg=bg_color, bold=True, dim=True, underline=True) == ansi_str


def test_style_color_not_exist():
    base_str = HELLO_WORLD

    with pytest.raises(ValueError):
        ansi.style(base_str, fg='fake', bg='green')

    with pytest.raises(ValueError):
        ansi.style(base_str, fg='blue', bg='fake')


def test_fg_lookup_exist():
    fg_color = 'green'
    assert ansi.fg_lookup(fg_color) == ansi.fg_lookup(ansi.fg.green)


def test_fg_lookup_nonexist():
    with pytest.raises(ValueError):
        ansi.fg_lookup('foo')


def test_bg_lookup_exist():
    bg_color = 'red'
    assert ansi.bg_lookup(bg_color) == ansi.bg_lookup(ansi.bg.red)


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


def test_cast_color_as_str():
    assert str(ansi.fg.blue) == ansi.fg.blue.value
    assert str(ansi.bg.blue) == ansi.bg.blue.value


def test_color_str_building():
    from cmd2.ansi import fg, bg
    assert fg.blue + "hello" == fg.blue.value + "hello"
    assert bg.blue + "hello" == bg.blue.value + "hello"
    assert fg.blue + "hello" + fg.reset == fg.blue.value + "hello" + fg.reset.value
    assert bg.blue + "hello" + bg.reset == bg.blue.value + "hello" + bg.reset.value
    assert fg.blue + bg.white + "hello" + fg.reset + bg.reset == \
           fg.blue.value + bg.white.value + "hello" + fg.reset.value + bg.reset.value


def test_color_nonunique_values():
    class Matching(ansi.ColorBase):
        magenta = ansi.fg_lookup('magenta')
        purple = ansi.fg_lookup('magenta')
    assert sorted(Matching.colors()) == ['magenta', 'purple']


def test_color_enum():
    assert ansi.fg_lookup('bright_red') == ansi.fg_lookup(ansi.fg.bright_red)
    assert ansi.bg_lookup('green') == ansi.bg_lookup(ansi.bg.green)


def test_colors_list():
    assert list(ansi.fg.__members__.keys()) == ansi.fg.colors()
    assert list(ansi.bg.__members__.keys()) == ansi.bg.colors()
