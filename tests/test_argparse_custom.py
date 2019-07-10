# flake8: noqa E302
"""
Unit/functional testing for argparse customizations in cmd2
"""
import argparse

import pytest

import cmd2
from cmd2.argparse_custom import Cmd2ArgParser
from .conftest import run_cmd


class ApCustomTestApp(cmd2.Cmd):
    """Test app for cmd2's argparse customization"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    range_parser = Cmd2ArgParser()
    range_parser.add_argument('--arg1', nargs=(2, 3))
    range_parser.add_argument('--arg2', nargs=argparse.ZERO_OR_MORE)
    range_parser.add_argument('--arg3', nargs=argparse.ONE_OR_MORE)

    @cmd2.with_argparser(range_parser)
    def do_range(self, _):
        pass


@pytest.fixture
def cust_app():
    return ApCustomTestApp()


def fake_func():
    pass


@pytest.mark.parametrize('args, is_valid', [
    ({'choices': []}, True),
    ({'choices_function': fake_func}, True),
    ({'choices_method': fake_func}, True),
    ({'completer_function': fake_func}, True),
    ({'completer_method': fake_func}, True),
    ({'choices': [], 'choices_function': fake_func}, False),
    ({'choices': [], 'choices_method': fake_func}, False),
    ({'choices_method': fake_func, 'completer_function': fake_func}, False),
    ({'choices_method': fake_func, 'completer_method': fake_func}, False),
])
def test_apcustom_invalid_args(args, is_valid):
    parser = Cmd2ArgParser(prog='test')
    try:
        parser.add_argument('name', **args)
        assert is_valid
    except ValueError as ex:
        assert not is_valid
        assert 'Only one of the following may be used' in str(ex)


def test_apcustom_usage():
    usage = "A custom usage statement"
    parser = Cmd2ArgParser(usage=usage)
    help = parser.format_help()
    assert usage in help


def test_apcustom_nargs_help_format(cust_app):
    out, err = run_cmd(cust_app, 'help range')
    assert 'Usage: range [-h] [--arg1 ARG1{2..3}] [--arg2 [ARG2 [...]]]' in out[0]
    assert '             [--arg3 ARG3 [...]]' in out[1]


def test_apcustom_nargs_not_enough(cust_app):
    out, err = run_cmd(cust_app, 'range --arg1 one')
    assert 'Error: argument --arg1: Expected between 2 and 3 arguments' in err[2]


def test_apcustom_narg_empty_tuple():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=())
    assert 'Ranged values for nargs must be a tuple of 2 integers' in str(excinfo.value)


def test_apcustom_narg_single_tuple():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(1,))
    assert 'Ranged values for nargs must be a tuple of 2 integers' in str(excinfo.value)


def test_apcustom_narg_tuple_triple():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(1, 2, 3))
    assert 'Ranged values for nargs must be a tuple of 2 integers' in str(excinfo.value)


def test_apcustom_narg_tuple_order():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(2, 1))
    assert 'Invalid nargs range. The first value must be less than the second' in str(excinfo.value)


def test_apcustom_narg_tuple_negative():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgParser(prog='test')
        parser.add_argument('invalid_tuple', nargs=(-1, 1))
    assert 'Negative numbers are invalid for nargs range' in str(excinfo.value)


def test_apcustom_narg_tuple_zero_base():
    parser = Cmd2ArgParser(prog='test')
    parser.add_argument('tuple', nargs=(0, 3))


def test_apcustom_narg_tuple_zero_to_one():
    parser = Cmd2ArgParser(prog='test')
    parser.add_argument('tuple', nargs=(0, 1))


def test_apcustom_print_message(capsys):
    import sys
    test_message = 'The test message'

    # Specify the file
    parser = Cmd2ArgParser(prog='test')
    parser._print_message(test_message, file=sys.stdout)
    out, err = capsys.readouterr()
    assert test_message in out

    # Make sure file defaults to sys.stderr
    parser = Cmd2ArgParser(prog='test')
    parser._print_message(test_message)
    out, err = capsys.readouterr()
    assert test_message in err


def test_apcustom_required_options():
    # Make sure a 'required arguments' section shows when a flag is marked required
    parser = Cmd2ArgParser(prog='test')
    parser.add_argument('--required_flag', required=True)
    help = parser.format_help()

    assert 'required arguments' in help
