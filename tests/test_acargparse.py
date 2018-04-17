"""
Unit/functional testing for readline tab-completion functions in the cmd2.py module.

These are primarily tests related to readline completer functions which handle tab-completion of cmd2/cmd commands,
file system paths, and shell commands.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import argparse
import os
import sys

import cmd2
from unittest import mock
import pytest
from AutoCompleter import ACArgumentParser

# Prefer statically linked gnureadline if available (for macOS compatibility due to issues with libedit)
try:
    import gnureadline as readline
except ImportError:
    # Try to import readline, but allow failure for convenience in Windows unit testing
    # Note: If this actually fails, you should install readline on Linux or Mac or pyreadline on Windows
    try:
        # noinspection PyUnresolvedReferences
        import readline
    except ImportError:
        pass


def test_acarg_narg_empty_tuple():
    with pytest.raises(ValueError) as excinfo:
        parser = ACArgumentParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=())
    assert 'Ranged values for nargs must be a tuple of 2 integers' in str(excinfo.value)


def test_acarg_narg_single_tuple():
    with pytest.raises(ValueError) as excinfo:
        parser = ACArgumentParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(1,))
    assert 'Ranged values for nargs must be a tuple of 2 integers' in str(excinfo.value)


def test_acarg_narg_tuple_triple():
    with pytest.raises(ValueError) as excinfo:
        parser = ACArgumentParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(1, 2, 3))
    assert 'Ranged values for nargs must be a tuple of 2 integers' in str(excinfo.value)


def test_acarg_narg_tuple_order():
    with pytest.raises(ValueError) as excinfo:
        parser = ACArgumentParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(2, 1))
    assert 'Invalid nargs range. The first value must be less than the second' in str(excinfo.value)


def test_acarg_narg_tuple_negative():
    with pytest.raises(ValueError) as excinfo:
        parser = ACArgumentParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(-1, 1))
    assert 'Negative numbers are invalid for nargs range' in str(excinfo.value)


def test_acarg_narg_tuple_zero_base():
    parser = ACArgumentParser(prog='test')
    parser.add_argument('tuple', nargs=(0, 3))


def test_acarg_narg_tuple_zero_to_one():
    parser = ACArgumentParser(prog='test')
    parser.add_argument('tuple', nargs=(0, 1))


