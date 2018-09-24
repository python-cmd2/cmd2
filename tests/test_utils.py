# coding=utf-8
"""
Unit testing for cmd2/utils.py module.

Copyright 2018 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import sys

import pytest

from colorama import Fore
import cmd2.utils as cu

HELLO_WORLD = 'Hello, world!'


def test_strip_ansi():
    base_str = HELLO_WORLD
    ansi_str = Fore.GREEN + base_str + Fore.RESET
    assert base_str != ansi_str
    assert base_str == cu.strip_ansi(ansi_str)

def test_strip_quotes_no_quotes():
    base_str = HELLO_WORLD
    stripped = cu.strip_quotes(base_str)
    assert base_str == stripped

def test_strip_quotes_with_quotes():
    base_str = '"' + HELLO_WORLD + '"'
    stripped = cu.strip_quotes(base_str)
    assert stripped == HELLO_WORLD

def test_remove_duplicates_no_duplicates():
    no_dups = [5, 4, 3, 2, 1]
    assert cu.remove_duplicates(no_dups) == no_dups

def test_remove_duplicates_with_duplicates():
    duplicates = [1, 1, 2, 3, 9, 9, 7, 8]
    assert cu.remove_duplicates(duplicates) == [1, 2, 3, 9, 7, 8]

def test_unicode_normalization():
    s1 = 'café'
    s2 = 'cafe\u0301'
    assert s1 != s2
    assert cu.norm_fold(s1) == cu.norm_fold(s2)

def test_unicode_casefold():
    micro = 'µ'
    micro_cf = micro.casefold()
    assert micro != micro_cf
    assert cu.norm_fold(micro) == cu.norm_fold(micro_cf)

def test_alphabetical_sort():
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'cafeteria']
    assert cu.alphabetical_sort(my_list) == ['A', 'cafeteria', 'café', 'micro', 'unity', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.alphabetical_sort(my_list) == ['a1', 'A11', 'A2', 'a22', 'a3']

def test_try_int_or_force_to_lower_case():
    str1 = '17'
    assert cu.try_int_or_force_to_lower_case(str1) == 17
    str1 = 'ABC'
    assert cu.try_int_or_force_to_lower_case(str1) == 'abc'
    str1 = 'X19'
    assert cu.try_int_or_force_to_lower_case(str1) == 'x19'
    str1 = ''
    assert cu.try_int_or_force_to_lower_case(str1) == ''

def test_natural_keys():
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['a1', 'A2', 'a3', 'A11', 'a22']

def test_natural_sort():
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    assert cu.natural_sort(my_list) == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.natural_sort(my_list) == ['a1', 'A2', 'a3', 'A11', 'a22']

def test_is_quoted_short():
    my_str = ''
    assert not cu.is_quoted(my_str)
    your_str = '"'
    assert not cu.is_quoted(your_str)

def test_is_quoted_yes():
    my_str = '"This is a test"'
    assert cu.is_quoted(my_str)
    your_str = "'of the emergengy broadcast system'"
    assert cu.is_quoted(your_str)

def test_is_quoted_no():
    my_str = '"This is a test'
    assert not cu.is_quoted(my_str)
    your_str = "of the emergengy broadcast system'"
    assert not cu.is_quoted(your_str)
    simple_str = "hello world"
    assert not cu.is_quoted(simple_str)

def test_quote_string_if_needed_yes():
    my_str = "Hello World"
    assert cu.quote_string_if_needed(my_str) == '"' + my_str + '"'
    your_str = '"foo" bar'
    assert cu.quote_string_if_needed(your_str) == "'" + your_str + "'"

def test_quot_string_if_needed_no():
    my_str = "HelloWorld"
    assert cu.quote_string_if_needed(my_str) == my_str
    your_str = "'Hello World'"
    assert cu.quote_string_if_needed(your_str) == your_str


@pytest.fixture
def stdout_sim():
    stdsim = cu.StdSim(sys.stdout)
    return stdsim

def test_stdsim_write_str(stdout_sim):
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str

def test_stdsim_write_bytes(stdout_sim):
    b_str = b'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.write(b_str)

def test_stdsim_buffer_write_bytes(stdout_sim):
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getvalue() == b_str.decode()

def test_stdsim_buffer_write_str(stdout_sim):
    my_str = 'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.buffer.write(my_str)

def test_stdsim_read(stdout_sim):
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    # getvalue() returns the value and leaves it unaffected internally
    assert stdout_sim.getvalue() == my_str
    # read() returns the value and then clears the internal buffer
    assert stdout_sim.read() == my_str
    assert stdout_sim.getvalue() == ''

def test_stdsim_clear(stdout_sim):
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str
    stdout_sim.clear()
    assert stdout_sim.getvalue() == ''
