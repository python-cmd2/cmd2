"""
Unit/functional testing for argparse customizations in cmd2

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""
import pytest
from cmd2.argparse_completer import ACArgumentParser


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
