"""Unit/functional testing for argparse customizations in cmd2"""

import argparse
import sys

import pytest

import cmd2
from cmd2 import (
    Choices,
    Cmd2ArgumentParser,
    argparse_custom,
    constants,
)
from cmd2.argparse_custom import (
    Cmd2HelpFormatter,
    generate_range_error,
    register_argparse_argument_parameter,
)
from cmd2.rich_utils import Cmd2RichArgparseConsole

from .conftest import run_cmd


class ApCustomTestApp(cmd2.Cmd):
    """Test app for cmd2's argparse customization"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    range_parser = Cmd2ArgumentParser()
    range_parser.add_argument('--arg0', nargs=1)
    range_parser.add_argument('--arg1', nargs=2)
    range_parser.add_argument('--arg2', nargs=(3,))
    range_parser.add_argument('--arg3', nargs=(2, 3))

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
def test_apcustom_completion_callable_count(kwargs, is_valid) -> None:
    parser = Cmd2ArgumentParser()
    if is_valid:
        parser.add_argument('name', **kwargs)
    else:
        expected_err = 'Only one of the following parameters'
        with pytest.raises(ValueError, match=expected_err):
            parser.add_argument('name', **kwargs)


@pytest.mark.parametrize('kwargs', [({'choices_provider': fake_func}), ({'completer': fake_func})])
def test_apcustom_no_completion_callable_alongside_choices(kwargs) -> None:
    parser = Cmd2ArgumentParser()

    expected_err = "None of the following parameters can be used alongside a choices parameter"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument('name', choices=['my', 'choices', 'list'], **kwargs)


@pytest.mark.parametrize('kwargs', [({'choices_provider': fake_func}), ({'completer': fake_func})])
def test_apcustom_no_completion_callable_when_nargs_is_0(kwargs) -> None:
    parser = Cmd2ArgumentParser()

    expected_err = "None of the following parameters can be used on an action that takes no arguments"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument('--name', action='store_true', **kwargs)


def test_apcustom_usage() -> None:
    usage = "A custom usage statement"
    parser = Cmd2ArgumentParser(usage=usage)
    assert usage in parser.format_help()


def test_apcustom_nargs_help_format(cust_app) -> None:
    out, _err = run_cmd(cust_app, 'help range')
    assert 'Usage: range [-h] [--arg0 ARG0] [--arg1 ARG1{2}] [--arg2 ARG2{3+}]' in out[0]
    assert '             [--arg3 ARG3{2..3}]' in out[1]


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
    ('nargs', 'expected_parts'),
    [
        # arg{2}
        (
            2,
            [("arg", True), ("{2}", False)],
        ),
        # arg{2+}
        (
            (2,),
            [("arg", True), ("{2+}", False)],
        ),
        # arg{0..5}
        (
            (0, 5),
            [("arg", True), ("{0..5}", False)],
        ),
    ],
)
def test_rich_metavar_parts(
    nargs: int | tuple[int, int | float],
    expected_parts: list[tuple[str, bool]],
) -> None:
    """
    Test cmd2's override of _rich_metavar_parts which handles custom nargs formats.

    :param nargs: the arguments nargs value
    :param expected_parts: list to compare to _rich_metavar_parts's return value

                           Each element in this list is a 2-item tuple.
                           item 1: one part of the argument string outputted by _format_args
                           item 2: boolean stating whether rich-argparse should color this part
    """
    parser = Cmd2ArgumentParser()
    help_formatter = parser._get_formatter()

    action = parser.add_argument("arg", nargs=nargs)  # type: ignore[arg-type]
    default_metavar = help_formatter._get_default_metavar_for_positional(action)

    parts = help_formatter._rich_metavar_parts(action, default_metavar)
    assert list(parts) == expected_parts


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
    assert arg.get_nargs_range() is None
    assert "[arg ...]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(0, 1))
    assert arg.nargs == argparse.OPTIONAL
    assert arg.get_nargs_range() is None
    assert "[arg]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(0, 3))
    assert arg.nargs == argparse.ZERO_OR_MORE
    assert arg.get_nargs_range() == (0, 3)
    assert "arg{0..3}" in parser.format_help()


def test_apcustom_narg_tuple_one_base() -> None:
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(1,))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() is None
    assert "arg [arg ...]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(1, 5))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() == (1, 5)
    assert "arg{1..5}" in parser.format_help()


def test_apcustom_narg_tuple_other_ranges() -> None:
    # Test range with no upper bound on max
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(2,))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() == (2, constants.INFINITY)

    # Test finite range
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument('arg', nargs=(2, 5))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() == (2, 5)


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
    err_msg = generate_range_error(1, constants.INFINITY)
    assert err_msg == "expected at least 1 argument"

    err_msg = generate_range_error(2, constants.INFINITY)
    assert err_msg == "expected at least 2 arguments"

    # min and max are equal
    err_msg = generate_range_error(1, 1)
    assert err_msg == "expected 1 argument"

    err_msg = generate_range_error(2, 2)
    assert err_msg == "expected 2 arguments"

    # min and max are not equal
    err_msg = generate_range_error(0, 1)
    assert err_msg == "expected 0 to 1 argument"

    err_msg = generate_range_error(0, 2)
    assert err_msg == "expected 0 to 2 arguments"


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


def test_register_argparse_argument_parameter() -> None:
    # Test successful registration
    param_name = "test_unique_param"
    register_argparse_argument_parameter(param_name)

    assert param_name in argparse_custom._CUSTOM_ACTION_ATTRIBS
    assert hasattr(argparse.Action, f'get_{param_name}')
    assert hasattr(argparse.Action, f'set_{param_name}')

    # Test duplicate registration
    expected_err = "already registered"
    with pytest.raises(KeyError, match=expected_err):
        register_argparse_argument_parameter(param_name)

    # Test invalid identifier
    expected_err = "must be a valid Python identifier"
    with pytest.raises(ValueError, match=expected_err):
        register_argparse_argument_parameter("invalid name")

    # Test collision with standard argparse.Action attribute
    expected_err = "conflicts with an existing attribute on argparse.Action"
    with pytest.raises(KeyError, match=expected_err):
        register_argparse_argument_parameter("format_usage")

    # Test collision with existing accessor methods
    try:
        argparse.Action.get_colliding_param = lambda self: None
        expected_err = "Accessor methods for 'colliding_param' already exist on argparse.Action"
        with pytest.raises(KeyError, match=expected_err):
            register_argparse_argument_parameter("colliding_param")
    finally:
        delattr(argparse.Action, 'get_colliding_param')

    # Test collision with internal attribute
    try:
        attr_name = constants.cmd2_attr_name("internal_collision")
        setattr(argparse.Action, attr_name, None)
        expected_err = f"The internal attribute '{attr_name}' already exists on argparse.Action"
        with pytest.raises(KeyError, match=expected_err):
            register_argparse_argument_parameter("internal_collision")
    finally:
        delattr(argparse.Action, attr_name)


def test_parser_attachment() -> None:
    # Attach a parser as a subcommand
    root_parser = Cmd2ArgumentParser(description="root command")
    root_subparsers = root_parser.add_subparsers()

    child_parser = Cmd2ArgumentParser(description="child command")
    root_subparsers.attach_parser(  # type: ignore[attr-defined]
        "child",
        child_parser,
        help="a child command",
        aliases=["child_alias"],
    )

    # Verify the same parser instance was used
    assert root_subparsers._name_parser_map["child"] is child_parser
    assert root_subparsers._name_parser_map["child_alias"] is child_parser

    # Verify an action with the help text exists
    child_action = None
    for action in root_subparsers._choices_actions:
        if action.dest == "child":
            child_action = action
            break
    assert child_action is not None
    assert child_action.help == "a child command"

    # Detatch the subcommand
    detached_parser = root_subparsers.detach_parser("child")  # type: ignore[attr-defined]

    # Verify subcommand and its aliases were removed
    assert detached_parser is child_parser
    assert "child" not in root_subparsers._name_parser_map
    assert "child_alias" not in root_subparsers._name_parser_map

    # Verify the help text action was removed
    choices_actions = [action.dest for action in root_subparsers._choices_actions]
    assert "child" not in choices_actions

    # Verify it returns None when subcommand does not exist
    assert root_subparsers.detach_parser("fake") is None  # type: ignore[attr-defined]


def test_completion_items_as_choices(capsys) -> None:
    """Test cmd2's patch to Argparse._check_value() which supports CompletionItems as choices.
    Choices are compared to CompletionItems.orig_value instead of the CompletionItem instance.
    """

    ##############################################################
    # Test CompletionItems with str values
    ##############################################################
    choices = Choices.from_values(["1", "2"])
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
    choices = Choices.from_values([1, 2])
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


def test_formatter_console() -> None:
    # self._console = console (inside console.setter)
    formatter = Cmd2HelpFormatter(prog='test')
    new_console = Cmd2RichArgparseConsole()
    formatter.console = new_console
    assert formatter._console is new_console


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Argparse didn't support color until Python 3.14",
)
def test_formatter_set_color(mocker) -> None:
    formatter = Cmd2HelpFormatter(prog='test')

    # return (inside _set_color if sys.version_info < (3, 14))
    mocker.patch('cmd2.argparse_custom.sys.version_info', (3, 13, 0))
    # This should return early without calling super()._set_color
    mock_set_color = mocker.patch('rich_argparse.RichHelpFormatter._set_color')
    formatter._set_color(True)
    mock_set_color.assert_not_called()

    # except TypeError and super()._set_color(color)
    mocker.patch('cmd2.argparse_custom.sys.version_info', (3, 15, 0))

    # Reset mock and make it raise TypeError when called with kwargs
    mock_set_color.reset_mock()

    def side_effect(color, **kwargs):
        if kwargs:
            raise TypeError("unexpected keyword argument 'file'")
        return

    mock_set_color.side_effect = side_effect

    # This call should trigger the TypeError and then the fallback call
    formatter._set_color(True, file=sys.stdout)

    # It should have been called twice: once with kwargs (failed) and once without (fallback)
    assert mock_set_color.call_count == 2
    mock_set_color.assert_any_call(True, file=sys.stdout)
    mock_set_color.assert_any_call(True)


def test_update_prog() -> None:
    """Test Cmd2ArgumentParser.update_prog() across various scenarios."""

    # Set up a complex parser hierarchy
    old_root = 'old_app'
    parser = Cmd2ArgumentParser(prog=old_root)

    # Positionals before subcommand
    parser.add_argument('pos1')

    # Mutually exclusive group with positionals
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('posA', nargs='?')
    group.add_argument('posB', nargs='?')

    # Subparsers with aliases and no help text
    subparsers = parser.add_subparsers(dest='cmd')

    # Subcommand with aliases
    sub1 = subparsers.add_parser('sub1', aliases=['s1', 'alias1'], help='help for sub1')

    # Subcommand with no help text
    sub2 = subparsers.add_parser('sub2')

    # Nested subparser
    sub2.add_argument('inner_pos')
    sub2_subparsers = sub2.add_subparsers(dest='sub2_cmd')
    leaf = sub2_subparsers.add_parser('leaf', help='leaf help')

    # Verify initial progs look correct
    assert parser.prog == 'old_app'
    assert sub1.prog == 'old_app pos1 (posA | posB) sub1'
    assert sub2.prog == 'old_app pos1 (posA | posB) sub2'
    assert leaf.prog == 'old_app pos1 (posA | posB) sub2 inner_pos leaf'

    # Perform update
    new_root = 'new_app'
    parser.update_prog(new_root)

    # Verify new progs look correct
    assert parser.prog == 'new_app'
    assert sub1.prog == 'new_app pos1 (posA | posB) sub1'
    assert sub2.prog == 'new_app pos1 (posA | posB) sub2'
    assert leaf.prog == 'new_app pos1 (posA | posB) sub2 inner_pos leaf'

    # Verify that action._prog_prefix was updated by adding a new subparser
    sub3 = subparsers.add_parser('sub3')
    assert sub3.prog == 'new_app pos1 (posA | posB) sub3'

    # Verify aliases still point to the correct parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            assert action.choices['s1'].prog == sub1.prog
            assert action.choices['alias1'].prog == sub1.prog
