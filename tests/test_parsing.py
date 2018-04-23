# coding=utf-8
"""
Unit/functional testing for helper functions/classes in the cmd2.py module.

These are primarily tests related to parsing.  Moreover, they are mostly a port of the old doctest tests which were
problematic because they worked properly for some versions of pyparsing but not for others.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import sys

import cmd2
import pytest


@pytest.fixture
def hist():
    from cmd2.cmd2 import HistoryItem
    h = cmd2.cmd2.History([HistoryItem('first'), HistoryItem('second'), HistoryItem('third'), HistoryItem('fourth')])
    return h

def test_history_span(hist):
    h = hist
    assert h == ['first', 'second', 'third', 'fourth']
    assert h.span('-2..') == ['third', 'fourth']
    assert h.span('2..3') == ['second', 'third']    # Inclusive of end
    assert h.span('3') == ['third']
    assert h.span(':') == h
    assert h.span('2..') == ['second', 'third', 'fourth']
    assert h.span('-1') == ['fourth']
    assert h.span('-2..-3') == ['third', 'second']
    assert h.span('*') == h

def test_history_get(hist):
    h = hist
    assert h == ['first', 'second', 'third', 'fourth']
    assert h.get('') == h
    assert h.get('-2') == h[:-2]
    assert h.get('5') == []
    assert h.get('2-3') == ['second']           # Exclusive of end
    assert h.get('ir') == ['first', 'third']    # Normal string search for all elements containing "ir"
    assert h.get('/i.*d/') == ['third']         # Regex string search "i", then anything, then "d"


def test_cast():
    cast = cmd2.cmd2.cast

    # Boolean
    assert cast(True, True) == True
    assert cast(True, False) == False
    assert cast(True, 0) == False
    assert cast(True, 1) == True
    assert cast(True, 'on') == True
    assert cast(True, 'off') == False
    assert cast(True, 'ON') == True
    assert cast(True, 'OFF') == False
    assert cast(True, 'y') == True
    assert cast(True, 'n') == False
    assert cast(True, 't') == True
    assert cast(True, 'f') == False

    # Non-boolean same type
    assert cast(1, 5) == 5
    assert cast(3.4, 2.7) == 2.7
    assert cast('foo', 'bar') == 'bar'
    assert cast([1,2], [3,4]) == [3,4]


def test_cast_problems(capsys):
    cast = cmd2.cmd2.cast

    expected = 'Problem setting parameter (now {}) to {}; incorrect type?\n'

    # Boolean current, with new value not convertible to bool
    current = True
    new = [True, True]
    assert cast(current, new) == current
    out, err = capsys.readouterr()
    assert out == expected.format(current, new)

    # Non-boolean current, with new value not convertible to current type
    current = 1
    new = 'octopus'
    assert cast(current, new) == current
    out, err = capsys.readouterr()
    assert out == expected.format(current, new)

def test_empty_statement_raises_exception():
    app = cmd2.Cmd()
    with pytest.raises(cmd2.cmd2.EmptyStatement):
        app._complete_statement('')

    with pytest.raises(cmd2.cmd2.EmptyStatement):
        app._complete_statement(' ')
