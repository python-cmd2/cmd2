"""Unit/functional testing for argparse customizations in cmd2"""

import argparse
import sys

import pytest

import cmd2
from cmd2 import (
    Choices,
    Cmd2ArgumentParser,
    argparse_utils,
    constants,
)
from cmd2.argparse_utils import (
    build_range_error,
    register_argparse_argument_parameter,
)

from .conftest import run_cmd


class ApCustomTestApp(cmd2.Cmd):
    """Test app for cmd2's argparse customization"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    range_parser = Cmd2ArgumentParser()
    range_parser.add_argument("--arg0", nargs=1)
    range_parser.add_argument("--arg1", nargs=2)
    range_parser.add_argument("--arg2", nargs=(3,))
    range_parser.add_argument("--arg3", nargs=(2, 3))

    @cmd2.with_argparser(range_parser)
    def do_range(self, _) -> None:
        pass


@pytest.fixture
def cust_app():
    return ApCustomTestApp()


def fake_func() -> None:
    pass


@pytest.mark.parametrize(
    ("kwargs", "is_valid"),
    [
        ({"choices_provider": fake_func}, True),
        ({"completer": fake_func}, True),
        ({"choices_provider": fake_func, "completer": fake_func}, False),
    ],
)
def test_apcustom_completion_callable_count(kwargs, is_valid) -> None:
    parser = Cmd2ArgumentParser()
    if is_valid:
        parser.add_argument("name", **kwargs)
    else:
        expected_err = "Only one of the following parameters"
        with pytest.raises(ValueError, match=expected_err):
            parser.add_argument("name", **kwargs)


@pytest.mark.parametrize("kwargs", [({"choices_provider": fake_func}), ({"completer": fake_func})])
def test_apcustom_no_completion_callable_alongside_choices(kwargs) -> None:
    parser = Cmd2ArgumentParser()

    expected_err = "None of the following parameters can be used alongside a choices parameter"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument("name", choices=["my", "choices", "list"], **kwargs)


@pytest.mark.parametrize("kwargs", [({"choices_provider": fake_func}), ({"completer": fake_func})])
def test_apcustom_no_completion_callable_when_nargs_is_0(kwargs) -> None:
    parser = Cmd2ArgumentParser()

    expected_err = "None of the following parameters can be used on an action that takes no arguments"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument("--name", action="store_true", **kwargs)


def test_apcustom_usage() -> None:
    usage = "A custom usage statement"
    parser = Cmd2ArgumentParser(usage=usage)
    assert usage in parser.format_help()


def test_apcustom_nargs_help_format(cust_app) -> None:
    out, _err = run_cmd(cust_app, "help range")
    assert "Usage: range [-h] [--arg0 ARG0] [--arg1 ARG1{2}] [--arg2 ARG2{3+}]" in out[0]
    assert "             [--arg3 ARG3{2..3}]" in out[1]


def test_apcustom_nargs_range_validation(cust_app) -> None:
    # nargs = (3,)  # noqa: ERA001
    _out, err = run_cmd(cust_app, "range --arg2 one two")
    assert "Error: argument --arg2: expected at least 3 arguments" in err[2]

    _out, err = run_cmd(cust_app, "range --arg2 one two three")
    assert not err

    _out, err = run_cmd(cust_app, "range --arg2 one two three four")
    assert not err

    # nargs = (2,3)  # noqa: ERA001
    _out, err = run_cmd(cust_app, "range --arg3 one")
    assert "Error: argument --arg3: expected 2 to 3 arguments" in err[2]

    _out, err = run_cmd(cust_app, "range --arg3 one two")
    assert not err

    _out, err = run_cmd(cust_app, "range --arg2 one two three")
    assert not err


@pytest.mark.parametrize(
    ("nargs", "expected_parts"),
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
    "nargs_tuple",
    [
        (),
        ("f", 5),
        (5, "f"),
        (1, 2, 3),
    ],
)
def test_apcustom_narg_invalid_tuples(nargs_tuple) -> None:
    parser = Cmd2ArgumentParser()
    expected_err = "Ranged values for nargs must be a tuple of 1 or 2 integers"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument("invalid_tuple", nargs=nargs_tuple)


def test_apcustom_narg_tuple_order() -> None:
    parser = Cmd2ArgumentParser()
    expected_err = "Invalid nargs range. The first value must be less than the second"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument("invalid_tuple", nargs=(2, 1))


def test_apcustom_narg_tuple_negative() -> None:
    parser = Cmd2ArgumentParser()
    expected_err = "Negative numbers are invalid for nargs range"
    with pytest.raises(ValueError, match=expected_err):
        parser.add_argument("invalid_tuple", nargs=(-1, 1))


def test_apcustom_narg_tuple_zero_base() -> None:
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(0,))
    assert arg.nargs == argparse.ZERO_OR_MORE
    assert arg.get_nargs_range() is None
    assert "[arg ...]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(0, 1))
    assert arg.nargs == argparse.OPTIONAL
    assert arg.get_nargs_range() is None
    assert "[arg]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(0, 3))
    assert arg.nargs == argparse.ZERO_OR_MORE
    assert arg.get_nargs_range() == (0, 3)
    assert "arg{0..3}" in parser.format_help()


def test_apcustom_narg_tuple_one_base() -> None:
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(1,))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() is None
    assert "arg [arg ...]" in parser.format_help()

    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(1, 5))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() == (1, 5)
    assert "arg{1..5}" in parser.format_help()


def test_apcustom_narg_tuple_other_ranges() -> None:
    # Test range with no upper bound on max
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(2,))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() == (2, constants.INFINITY)

    # Test finite range
    parser = Cmd2ArgumentParser()
    arg = parser.add_argument("arg", nargs=(2, 5))
    assert arg.nargs == argparse.ONE_OR_MORE
    assert arg.get_nargs_range() == (2, 5)


def test_apcustom_print_message(capsys) -> None:
    test_message = "The test message"

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


def test_build_range_error() -> None:
    # max is INFINITY
    err_msg = build_range_error(1, constants.INFINITY)
    assert err_msg == "expected at least 1 argument"

    err_msg = build_range_error(2, constants.INFINITY)
    assert err_msg == "expected at least 2 arguments"

    # min and max are equal
    err_msg = build_range_error(1, 1)
    assert err_msg == "expected 1 argument"

    err_msg = build_range_error(2, 2)
    assert err_msg == "expected 2 arguments"

    # min and max are not equal
    err_msg = build_range_error(0, 1)
    assert err_msg == "expected 0 to 1 argument"

    err_msg = build_range_error(0, 2)
    assert err_msg == "expected 0 to 2 arguments"


def test_apcustom_metavar_tuple() -> None:
    # Test the case when a tuple metavar is used with nargs an integer > 1
    parser = Cmd2ArgumentParser()
    parser.add_argument("--aflag", nargs=2, metavar=("foo", "bar"), help="This is a test")
    assert "[--aflag foo bar]" in parser.format_help()


def test_register_argparse_argument_parameter() -> None:
    # Test successful registration
    param_name = "test_unique_param"
    register_argparse_argument_parameter(param_name)

    assert param_name in argparse_utils._CUSTOM_ACTION_ATTRIBS
    assert hasattr(argparse.Action, f"get_{param_name}")
    assert hasattr(argparse.Action, f"set_{param_name}")

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
        delattr(argparse.Action, "get_colliding_param")

    # Test collision with internal attribute
    try:
        attr_name = constants.cmd2_private_attr_name("internal_collision")
        setattr(argparse.Action, attr_name, None)
        expected_err = f"The internal attribute '{attr_name}' already exists on argparse.Action"
        with pytest.raises(KeyError, match=expected_err):
            register_argparse_argument_parameter("internal_collision")
    finally:
        delattr(argparse.Action, attr_name)


def test_subcommand_attachment() -> None:
    """Test Cmd2ArgumentParser convenience methods for attaching and detaching subcommands."""

    ###############################
    # Set up parsers
    ###############################
    root_parser = Cmd2ArgumentParser(prog="root", description="root command")
    root_subparsers = root_parser.add_subparsers()

    child_parser = Cmd2ArgumentParser(prog="child", description="child command")
    child_subparsers = child_parser.add_subparsers()  # Must have subparsers to host grandchild

    grandchild_parser = Cmd2ArgumentParser(prog="grandchild", description="grandchild command")

    ###############################
    # Attach subcommands
    ###############################

    # Attach child to root
    root_parser.attach_subcommand(
        [],
        "child",
        child_parser,
        help="a child command",
        aliases=["child_alias"],
    )

    # Attach grandchild to child
    root_parser.attach_subcommand(
        ["child"],
        "grandchild",
        grandchild_parser,
        help="a grandchild command",
    )

    ###############################
    # Verify hierarchy navigation
    ###############################

    assert root_parser._find_parser(["child", "grandchild"]) is grandchild_parser
    assert root_parser._find_parser(["child"]) is child_parser
    assert root_parser._find_parser([]) is root_parser

    ###############################
    # Verify attachments
    ###############################

    # Verify child attachment and aliases
    assert root_subparsers._name_parser_map["child"] is child_parser
    assert root_subparsers._name_parser_map["child_alias"] is child_parser

    # Verify grandchild attachment
    assert child_subparsers._name_parser_map["grandchild"] is grandchild_parser

    ###############################
    # Detach subcommands
    ###############################

    # Detach grandchild from child
    detached_grandchild = root_parser.detach_subcommand(["child"], "grandchild")
    assert detached_grandchild is grandchild_parser
    assert "grandchild" not in child_subparsers._name_parser_map

    # Detach child from root
    detached_child = root_parser.detach_subcommand([], "child")
    assert detached_child is child_parser
    assert "child" not in root_subparsers._name_parser_map
    assert "child_alias" not in root_subparsers._name_parser_map


def test_subcommand_attachment_errors() -> None:
    root_parser = Cmd2ArgumentParser(prog="root", description="root command")
    child_parser = Cmd2ArgumentParser(prog="child", description="child command")

    # Verify ValueError when subcommands are not supported
    with pytest.raises(ValueError, match="Command 'root' does not support subcommands"):
        root_parser.attach_subcommand([], "anything", child_parser)
    with pytest.raises(ValueError, match="Command 'root' does not support subcommands"):
        root_parser.detach_subcommand([], "anything")

    # Allow subcommands for the next tests
    root_parser.add_subparsers()

    # Verify ValueError when path is invalid (_find_parser() fails)
    with pytest.raises(ValueError, match="Subcommand 'nonexistent' not found"):
        root_parser.attach_subcommand(["nonexistent"], "anything", child_parser)
    with pytest.raises(ValueError, match="Subcommand 'nonexistent' not found"):
        root_parser.detach_subcommand(["nonexistent"], "anything")

    # Verify ValueError when path is valid but subcommand name is wrong
    with pytest.raises(ValueError, match="Subcommand 'fake' not found in 'root'"):
        root_parser.detach_subcommand([], "fake")

    # Verify TypeError when attaching a non-Cmd2ArgumentParser type
    ap_parser = argparse.ArgumentParser(prog="non-cmd2-parser")
    with pytest.raises(TypeError, match=r"must be an instance of 'Cmd2ArgumentParser' \(or a subclass\)"):
        root_parser.attach_subcommand([], "sub", ap_parser)  # type: ignore[arg-type]


def test_subcommand_attachment_parser_class_override() -> None:
    class MyParser(Cmd2ArgumentParser):
        pass

    class MySubParser(MyParser):
        pass

    root_parser = Cmd2ArgumentParser(prog="root")

    # Explicitly override parser_class for this subparsers action
    root_parser.add_subparsers(parser_class=MyParser)

    # Attaching a MyParser instance should succeed
    my_parser = MyParser(prog="sub")
    root_parser.attach_subcommand([], "sub", my_parser)

    # Attaching a MySubParser instance should also succeed (isinstance check)
    my_sub_parser = MySubParser(prog="sub2")
    root_parser.attach_subcommand([], "sub2", my_sub_parser)

    # Attaching a standard Cmd2ArgumentParser instance should fail
    standard_parser = Cmd2ArgumentParser(prog="standard")
    with pytest.raises(TypeError, match=r"must be an instance of 'MyParser' \(or a subclass\)"):
        root_parser.attach_subcommand([], "fail", standard_parser)


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
    args = parser.parse_args(["1"])
    assert args.choices_arg == "1"

    args = parser.parse_args(["2"])
    assert args.choices_arg == "2"

    # Next test invalid choice
    with pytest.raises(SystemExit):
        args = parser.parse_args(["3"])

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
    args = parser.parse_args(["1"])
    assert args.choices_arg == 1

    args = parser.parse_args(["2"])
    assert args.choices_arg == 2

    # Next test invalid choice
    with pytest.raises(SystemExit):
        args = parser.parse_args(["3"])

    # Confirm error text contains correct value type of int
    _out, err = capsys.readouterr()
    assert "invalid choice: 3 (choose from 1, 2)" in err


def test_update_prog() -> None:
    """Test Cmd2ArgumentParser.update_prog() across various scenarios."""

    # Set up a complex parser hierarchy
    old_app = "old_app"
    root = Cmd2ArgumentParser(prog=old_app)

    # Positionals before subcommand
    root.add_argument("pos1")

    # Mutually exclusive group with positionals
    group = root.add_mutually_exclusive_group(required=True)
    group.add_argument("posA", nargs="?")
    group.add_argument("posB", nargs="?")

    # Subparsers with aliases and no help text
    root_subparsers = root.add_subparsers(dest="cmd")

    # Subcommand with aliases
    sub1 = root_subparsers.add_parser("sub1", aliases=["s1", "alias1"], help="help for sub1")

    # Subcommand with no help text
    sub2 = root_subparsers.add_parser("sub2")

    # Nested subparser
    sub2.add_argument("inner_pos")
    sub2_subparsers = sub2.add_subparsers(dest="sub2_cmd")
    leaf = sub2_subparsers.add_parser("leaf", help="leaf help")

    # Save initial prog values
    orig_root_prog = root.prog
    orig_sub1_prog = sub1.prog
    orig_sub2_prog = sub2.prog
    orig_leaf_prog = leaf.prog

    # Perform update
    new_app = "new_app"
    root.update_prog(new_app)

    # Verify updated prog values
    assert root.prog.startswith(new_app)
    assert root.prog == orig_root_prog.replace(old_app, new_app, 1)

    assert sub1.prog.startswith(new_app)
    assert sub1.prog == orig_sub1_prog.replace(old_app, new_app, 1)

    assert sub2.prog.startswith(new_app)
    assert sub2.prog == orig_sub2_prog.replace(old_app, new_app, 1)

    assert leaf.prog.startswith(new_app)
    assert leaf.prog == orig_leaf_prog.replace(old_app, new_app, 1)

    # Verify that action._prog_prefix was updated by adding a new subparser
    sub3 = root_subparsers.add_parser("sub3")
    assert sub3.prog.startswith(new_app)
    assert sub3.prog == root_subparsers._prog_prefix + " sub3"

    # Verify aliases still point to the correct parser
    for action in root._actions:
        if isinstance(action, argparse._SubParsersAction):
            assert action.choices["s1"].prog == sub1.prog
            assert action.choices["alias1"].prog == sub1.prog
