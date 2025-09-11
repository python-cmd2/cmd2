"""Unit/functional testing for argparse customizations in cmd2"""

import argparse

import pytest

import cmd2
from cmd2 import (
    Cmd2ArgumentParser,
    constants,
)
from cmd2.argparse_custom import (
    generate_range_error,
)

from .conftest import (
    run_cmd,
)


class ApCustomTestApp(cmd2.Cmd):
    """Test app for cmd2's argparse customization"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    range_parser = Cmd2ArgumentParser()
    range_parser.add_argument('--arg0', nargs=1)
    range_parser.add_argument('--arg1', nargs=2)
    range_parser.add_argument('--arg2', nargs=(3,))
    range_parser.add_argument('--arg3', nargs=(2, 3))
    range_parser.add_argument('--arg4', nargs=argparse.ZERO_OR_MORE)
    range_parser.add_argument('--arg5', nargs=argparse.ONE_OR_MORE)

    @cmd2.with_argparser(range_parser)
    def do_range(self, _) -> None:
        pass


@pytest.fixture
def cust_app():
    return ApCustomTestApp()


def fake_func() -> None:
    pass


@pytest.mark.parametrize(
    ('kwargs', 'is_valid'),
    [
        ({'choices_provider': fake_func}, True),
        ({'completer': fake_func}, True),
        ({'choices_provider': fake_func, 'completer': fake_func}, False),
    ],
)
def test_apcustom_choices_callable_count(kwargs, is_valid) -> None:
    parser = Cmd2ArgumentParser()
    if is_valid:
        parser.add_argument('name', **kwargs)
    else:
        expected_err = 'Only one of the following parameters'
        with pytest.raises(ValueError, match=expected_err):
            parser.add_argument('name', **kwargs)


@pytest.mark.parametrize('kwargs', [({'choices_provider': fake_func}), ({'completer': fake_func})])
def test_apcustom_no_choices_callables_alongside_choices(kwargs) -> None:
    parser = Cmd2ArgumentParser()
    with pytest.raises(TypeError) as excinfo:
        parser.add_argument('name', choices=['my', 'choices', 'list'], **kwargs)
    assert 'None of the following parameters can be used alongside a choices parameter' in str(excinfo.value)


@pytest.mark.parametrize('kwargs', [({'choices_provider': fake_func}), ({'completer': fake_func})])
def test_apcustom_no_choices_callables_when_nargs_is_0(kwargs) -> None:
    parser = Cmd2ArgumentParser()
    with pytest.raises(TypeError) as excinfo:
        parser.add_argument('--name', action='store_true', **kwargs)
    assert 'None of the following parameters can be used on an action that takes no arguments' in str(excinfo.value)


def test_apcustom_usage() -> None:
    usage = "A custom usage statement"
    parser = Cmd2ArgumentParser(usage=usage)
    assert usage in parser.format_help()


def test_apcustom_nargs_help_format(cust_app) -> None:
    out, _err = run_cmd(cust_app, 'help range')
    assert 'Usage: range [-h] [--arg0 ARG0] [--arg1 ARG1{2}] [--arg2 ARG2{3+}]' in out[0]
    assert '             [--arg3 ARG3{2..3}] [--arg4 [ARG4 [...]]] [--arg5 ARG5 [...]]' in out[1]


def test_apcustom_nargs_range_validation(cust_app) -> None:
    # nargs = (3,)  # noqa: ERA001
    _out, err = run_cmd(cust_app, 'range --arg2 one two')
    assert 'Error: argument --arg2: expected at least 3 arguments' in err[2]

    _out, err = run_cmd(cust_app, 'range --arg2 one two three')
    assert not err

    _out, err = run_cmd(cust_app, 'range --arg2 one two three four')
    assert not err

    # nargs = (2,3)  # noqa: ERA001
    _out, err = run_cmd(cust_app, 'range --arg3 one')
    assert 'Error: argument --arg3: expected 2 to 3 arguments' in err[2]

    _out, err = run_cmd(cust_app, 'range --arg3 one two')
    assert not err

    _out, err = run_cmd(cust_app, 'range --arg2 one two three')
    assert not err


@pytest.mark.parametrize(
    'nargs_tuple',
    [
        (),
        ('f', 5),
        (5, 'f'),
        (1, 2, 3),
    ],
)
def test_apcustom_narg_invalid_tuples(nargs_tuple) -> None:
    parser = Cmd2ArgumentParser()
    expected_err = 'Ranged values for nargs must be a tuple of 1 or 2 integers'
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument('invalid_tuple', nargs=nargs_tuple)


def test_apcustom_narg_tuple_order() -> None:
    parser = Cmd2ArgumentParser()
    expected_err = 'Invalid nargs range. The first value must be less than the second'
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument('invalid_tuple', nargs=(2, 1))


def test_apcustom_narg_tuple_negative() -> None:
    parser = Cmd2ArgumentParser()
    expected_err = 'Negative numbers are invalid for nargs range'
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument('invalid_tuple', nargs=(-1, 1))


def test_apcustom_narg_tuple_zero_base() -> None:
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


def test_apcustom_narg_tuple_one_base() -> None:
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


def test_apcustom_narg_tuple_other_ranges() -> None:
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


def test_apcustom_print_message(capsys) -> None:
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


def test_generate_range_error() -> None:
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


def test_apcustom_required_options() -> None:
    # Make sure a 'required arguments' section shows when a flag is marked required
    parser = Cmd2ArgumentParser()
    parser.add_argument('--required_flag', required=True)
    assert 'Required Arguments' in parser.format_help()


def test_apcustom_metavar_tuple() -> None:
    # Test the case when a tuple metavar is used with nargs an integer > 1
    parser = Cmd2ArgumentParser()
    parser.add_argument('--aflag', nargs=2, metavar=('foo', 'bar'), help='This is a test')
    assert '[--aflag foo bar]' in parser.format_help()


def test_cmd2_attribute_wrapper() -> None:
    initial_val = 5
    wrapper = cmd2.Cmd2AttributeWrapper(initial_val)
    assert wrapper.get() == initial_val

    new_val = 22
    wrapper.set(new_val)
    assert wrapper.get() == new_val


def test_completion_items_as_choices(capsys) -> None:
    """Test cmd2's patch to Argparse._check_value() which supports CompletionItems as choices.
    Choices are compared to CompletionItems.orig_value instead of the CompletionItem instance.
    """
    from cmd2.argparse_custom import (
        CompletionItem,
    )

    ##############################################################
    # Test CompletionItems with str values
    ##############################################################
    choices = [CompletionItem("1", "Description One"), CompletionItem("2", "Two")]
    parser = Cmd2ArgumentParser()
    parser.add_argument("choices_arg", type=str, choices=choices)

    # First test valid choices. Confirm the parsed data matches the correct type of str.
    args = parser.parse_args(['1'])
    assert args.choices_arg == '1'

    args = parser.parse_args(['2'])
    assert args.choices_arg == '2'

    # Next test invalid choice
    with pytest.raises(SystemExit):
        args = parser.parse_args(['3'])

    # Confirm error text contains correct value type of str
    _out, err = capsys.readouterr()
    assert "invalid choice: '3' (choose from '1', '2')" in err

    ##############################################################
    # Test CompletionItems with int values
    ##############################################################
    choices = [CompletionItem(1, "Description One"), CompletionItem(2, "Two")]
    parser = Cmd2ArgumentParser()
    parser.add_argument("choices_arg", type=int, choices=choices)

    # First test valid choices. Confirm the parsed data matches the correct type of int.
    args = parser.parse_args(['1'])
    assert args.choices_arg == 1

    args = parser.parse_args(['2'])
    assert args.choices_arg == 2

    # Next test invalid choice
    with pytest.raises(SystemExit):
        args = parser.parse_args(['3'])

    # Confirm error text contains correct value type of int
    _out, err = capsys.readouterr()
    assert 'invalid choice: 3 (choose from 1, 2)' in err
