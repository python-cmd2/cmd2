# flake8: noqa E302
"""
Unit/functional testing for argparse customizations in cmd2
"""
import argparse

import pytest

import cmd2
from cmd2 import Cmd2ArgumentParser, constants
from cmd2.argparse_custom import generate_range_error

from .conftest import run_cmd


class ApCustomTestApp(cmd2.Cmd):
    """Test app for cmd2's argparse customization"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    range_parser = Cmd2ArgumentParser()
    range_parser.add_argument('--arg0', nargs=1)
    range_parser.add_argument('--arg1', nargs=2)
    range_parser.add_argument('--arg2', nargs=(3,))
    range_parser.add_argument('--arg3', nargs=(2, 3))
    range_parser.add_argument('--arg4', nargs=argparse.ZERO_OR_MORE)
    range_parser.add_argument('--arg5', nargs=argparse.ONE_OR_MORE)

    @cmd2.with_argparser(range_parser)
    def do_range(self, _):
        pass


@pytest.fixture
def cust_app():
    return ApCustomTestApp()


def fake_func():
    pass


@pytest.mark.parametrize('kwargs, is_valid', [
    ({'choices_function': fake_func}, True),
    ({'choices_method': fake_func}, True),
    ({'completer_function': fake_func}, True),
    ({'completer_method': fake_func}, True),
    ({'choices_function': fake_func, 'choices_method': fake_func}, False),
    ({'choices_method': fake_func, 'completer_function': fake_func}, False),
    ({'completer_function': fake_func, 'completer_method': fake_func}, False),
])
def test_apcustom_choices_callable_count(kwargs, is_valid):
    parser = Cmd2ArgumentParser()
    try:
        parser.add_argument('name', **kwargs)
        assert is_valid
    except ValueError as ex:
        assert not is_valid
        assert 'Only one of the following parameters' in str(ex)


@pytest.mark.parametrize('kwargs', [
    ({'choices_function': fake_func}),
    ({'choices_method': fake_func}),
    ({'completer_function': fake_func}),
    ({'completer_method': fake_func})
])
def test_apcustom_no_choices_callables_alongside_choices(kwargs):
    with pytest.raises(TypeError) as excinfo:
        parser = Cmd2ArgumentParser()
        parser.add_argument('name', choices=['my', 'choices', 'list'], **kwargs)
    assert 'None of the following parameters can be used alongside a choices parameter' in str(excinfo.value)


@pytest.mark.parametrize('kwargs', [
    ({'choices_function': fake_func}),
    ({'choices_method': fake_func}),
    ({'completer_function': fake_func}),
    ({'completer_method': fake_func})
])
def test_apcustom_no_choices_callables_when_nargs_is_0(kwargs):
    with pytest.raises(TypeError) as excinfo:
        parser = Cmd2ArgumentParser()
        parser.add_argument('name', action='store_true', **kwargs)
    assert 'None of the following parameters can be used on an action that takes no arguments' in str(excinfo.value)


def test_apcustom_usage():
    usage = "A custom usage statement"
    parser = Cmd2ArgumentParser(usage=usage)
    assert usage in parser.format_help()


def test_apcustom_nargs_help_format(cust_app):
    out, err = run_cmd(cust_app, 'help range')
    assert 'Usage: range [-h] [--arg0 ARG0] [--arg1 ARG1{2}] [--arg2 ARG2{3+}]' in out[0]
    assert '             [--arg3 ARG3{2..3}] [--arg4 [ARG4 [...]]] [--arg5 ARG5 [...]]' in out[1]


def test_apcustom_nargs_range_validation(cust_app):
    # nargs = (3,)
    out, err = run_cmd(cust_app, 'range --arg2 one two')
    assert 'Error: argument --arg2: expected at least 3 arguments' in err[2]

    out, err = run_cmd(cust_app, 'range --arg2 one two three')
    assert not err

    out, err = run_cmd(cust_app, 'range --arg2 one two three four')
    assert not err

    # nargs = (2,3)
    out, err = run_cmd(cust_app, 'range --arg3 one')
    assert 'Error: argument --arg3: expected 2 to 3 arguments' in err[2]

    out, err = run_cmd(cust_app, 'range --arg3 one two')
    assert not err

    out, err = run_cmd(cust_app, 'range --arg2 one two three')
    assert not err


@pytest.mark.parametrize('nargs_tuple', [
    (),
    ('f', 5),
    (5, 'f'),
    (1, 2, 3),
])
def test_apcustom_narg_invalid_tuples(nargs_tuple):
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgumentParser()
        parser.add_argument('invalid_tuple', nargs=nargs_tuple)
    assert 'Ranged values for nargs must be a tuple of 1 or 2 integers' in str(excinfo.value)


def test_apcustom_narg_tuple_order():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgumentParser()
        parser.add_argument('invalid_tuple', nargs=(2, 1))
    assert 'Invalid nargs range. The first value must be less than the second' in str(excinfo.value)


def test_apcustom_narg_tuple_negative():
    with pytest.raises(ValueError) as excinfo:
        parser = Cmd2ArgumentParser()
        parser.add_argument('invalid_tuple', nargs=(-1, 1))
    assert 'Negative numbers are invalid for nargs range' in str(excinfo.value)


# noinspection PyUnresolvedReferences
def test_apcustom_narg_tuple_zero_base():
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(0,))
    assert arg.nargs == argparse.ZERO_OR_MORE
    assert arg.nargs_range is None
    assert "[arg [...]]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(0, 1))
    assert arg.nargs == argparse.OPTIONAL
    assert arg.nargs_range is None
    assert "[arg]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(0, 3))
    assert arg.nargs == argparse.ZERO_OR_MORE
    assert arg.nargs_range == (0, 3)
    assert "arg{0..3}" in parser.format_help()


# noinspection PyUnresolvedReferences
def test_apcustom_narg_tuple_one_base():
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(1,))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.nargs_range is None
    assert "arg [...]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(1, 5))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.nargs_range == (1, 5)
    assert "arg{1..5}" in parser.format_help()


# noinspection PyUnresolvedReferences
def test_apcustom_narg_tuple_other_ranges():

    # Test range with no upper bound on max
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(2,))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.nargs_range == (2, constants.INFINITY)

    # Test finite range
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(2, 5))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.nargs_range == (2, 5)


def test_apcustom_print_message(capsys):
    import sys
    test_message = 'The test message'

    # Specify the file
    parser = Cmd2ArgumentParser()
    parser._print_message(test_message, file=sys.stdout)
    out, err = capsys.readouterr()
    assert test_message in out

    # Make sure file defaults to sys.stderr
    parser = Cmd2ArgumentParser()
    parser._print_message(test_message)
    out, err = capsys.readouterr()
    assert test_message in err


def test_generate_range_error():
    # max is INFINITY
    err_str = generate_range_error(1, constants.INFINITY)
    assert err_str == "expected at least 1 argument"

    err_str = generate_range_error(2, constants.INFINITY)
    assert err_str == "expected at least 2 arguments"

    # min and max are equal
    err_str = generate_range_error(1, 1)
    assert err_str == "expected 1 argument"

    err_str = generate_range_error(2, 2)
    assert err_str == "expected 2 arguments"

    # min and max are not equal
    err_str = generate_range_error(0, 1)
    assert err_str == "expected 0 to 1 argument"

    err_str = generate_range_error(0, 2)
    assert err_str == "expected 0 to 2 arguments"


def test_apcustom_required_options():
    # Make sure a 'required arguments' section shows when a flag is marked required
    parser = Cmd2ArgumentParser()
    parser.add_argument('--required_flag', required=True)
    assert 'required arguments' in parser.format_help()


def test_override_parser():
    import importlib
    from cmd2 import DEFAULT_ARGUMENT_PARSER

    # The standard parser is Cmd2ArgumentParser
    assert DEFAULT_ARGUMENT_PARSER == Cmd2ArgumentParser

    # Set our parser module and force a reload of cmd2 so it loads the module
    argparse.cmd2_parser_module = 'examples.custom_parser'
    importlib.reload(cmd2)
    from cmd2 import DEFAULT_ARGUMENT_PARSER

    # Verify DEFAULT_ARGUMENT_PARSER is now our CustomParser
    from examples.custom_parser import CustomParser
    assert DEFAULT_ARGUMENT_PARSER == CustomParser
