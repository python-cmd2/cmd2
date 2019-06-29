# coding=utf-8
# flake8: noqa E302
"""
Unit testing for cmd2/ansi.py module
"""
import pytest
from colorama import Fore, Back, Style

import cmd2.ansi as ansi

HELLO_WORLD = 'Hello, world!'


def test_strip_ansi():
    base_str = HELLO_WORLD
    ansi_str = Fore.GREEN + base_str + Fore.RESET
    assert base_str != ansi_str
    assert base_str == ansi.strip_ansi(ansi_str)


def test_ansi_safe_wcswidth():
    base_str = HELLO_WORLD
    ansi_str = Fore.GREEN + base_str + Fore.RESET
    assert ansi.ansi_safe_wcswidth(ansi_str) != len(ansi_str)


def test_style_none():
    base_str = HELLO_WORLD
    ansi_str = base_str
    assert ansi.style(base_str) == ansi_str


def test_style_fg():
    base_str = HELLO_WORLD
    ansi_str = Fore.BLUE + base_str + Fore.RESET
    assert ansi.style(base_str, fg='blue') == ansi_str


def test_style_bg():
    base_str = HELLO_WORLD
    ansi_str = Back.GREEN + base_str + Back.RESET
    assert ansi.style(base_str, bg='green') == ansi_str


def test_style_bold():
    base_str = HELLO_WORLD
    ansi_str = Style.BRIGHT + base_str + Style.NORMAL
    assert ansi.style(base_str, bold=True) == ansi_str


def test_style_underline():
    base_str = HELLO_WORLD
    ansi_str = ansi.UNDERLINE_ENABLE + base_str + ansi.UNDERLINE_DISABLE
    assert ansi.style(base_str, underline=True) == ansi_str


def test_style_multi():
    base_str = HELLO_WORLD
    ansi_str = Fore.BLUE + Back.GREEN + Style.BRIGHT + ansi.UNDERLINE_ENABLE + \
               base_str + Fore.RESET + Back.RESET + Style.NORMAL + ansi.UNDERLINE_DISABLE
    assert ansi.style(base_str, fg='blue', bg='green', bold=True, underline=True) == ansi_str


def test_style_color_not_exist():
    base_str = HELLO_WORLD

    with pytest.raises(ValueError):
        ansi.style(base_str, fg='fake', bg='green')

    with pytest.raises(ValueError):
        ansi.style(base_str, fg='blue', bg='fake')


def test_fg_lookup_exist():
    assert ansi.fg_lookup('green') == Fore.GREEN


def test_fg_lookup_nonexist():
    with pytest.raises(ValueError):
        ansi.fg_lookup('foo')


def test_bg_lookup_exist():
    assert ansi.bg_lookup('green') == Back.GREEN


def test_bg_lookup_nonexist():
    with pytest.raises(ValueError):
        ansi.bg_lookup('bar')
