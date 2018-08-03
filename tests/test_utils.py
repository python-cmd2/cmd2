# coding=utf-8
"""
Unit/functional testing for cmd2/utils.py module.

Copyright 2018 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
from colorama import Fore
import cmd2.utils as cu


def test_strip_ansi():
    base_str = 'Hello, world!'
    ansi_str =  Fore.GREEN + base_str + Fore.RESET
    assert base_str != ansi_str
    assert base_str == cu.strip_ansi(ansi_str)
