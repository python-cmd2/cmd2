"""reproduces test_argparse.py except with SubCommands"""

import pytest

import cmd2

from .conftest import (
    WithCommandSets,
    run_cmd,
)


class SubcommandSet(cmd2.CommandSet):
    """Example cmd2 application where we a base command which has a couple subcommands."""

    def __init__(self, dummy) -> None:
        super().__init__()

    # subcommand functions for the base command
    def base_foo(self, args) -> None:
        """Foo subcommand of base command"""
        self._cmd.poutput(args.x * args.y)

    def base_bar(self, args) -> None:
        """Bar subcommand of base command"""
        self._cmd.poutput(f'(({args.z}))')

    def base_helpless(self, args) -> None:
        """Helpless subcommand of base command"""
        self._cmd.poutput(f'(({args.z}))')

    # create the top-level parser for the base command
    base_parser = cmd2.Cmd2ArgumentParser()
    base_subparsers = base_parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND', required=True)

    # create the parser for the "foo" subcommand
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.set_defaults(func=base_foo)

    # create the parser for the "bar" subcommand
    parser_bar = base_subparsers.add_parser('bar', help='bar help', aliases=['bar_1', 'bar_2'])
    parser_bar.add_argument('z', help='string')
    parser_bar.set_defaults(func=base_bar)

    # create the parser for the "helpless" subcommand
    # This subcommand has aliases and no help text. It exists to prevent changes to set_parser_prog() which
    # use an approach which relies on action._choices_actions list. See comment in that function for more
    # details.
    parser_helpless = base_subparsers.add_parser('helpless', aliases=['helpless_1', 'helpless_2'])
    parser_helpless.add_argument('z', help='string')
    parser_helpless.set_defaults(func=base_helpless)

    @cmd2.with_argparser(base_parser)
    def do_base(self, args) -> None:
        """Base command help"""
        # Call whatever subcommand function was selected
        func = args.func
        func(self, args)


@pytest.fixture
def subcommand_app():
    return WithCommandSets(auto_load_commands=False, command_sets=[SubcommandSet(1)])


def test_subcommand_foo(subcommand_app) -> None:
    out, _err = run_cmd(subcommand_app, 'base foo -x2 5.0')
    assert out == ['10.0']


def test_subcommand_bar(subcommand_app) -> None:
    out, _err = run_cmd(subcommand_app, 'base bar baz')
    assert out == ['((baz))']


def test_subcommand_invalid(subcommand_app) -> None:
    _out, err = run_cmd(subcommand_app, 'base baz')
    assert err[0].startswith('Usage: base')
    assert err[1].startswith("Error: argument SUBCOMMAND: invalid choice: 'baz'")


def test_subcommand_base_help(subcommand_app) -> None:
    out, _err = run_cmd(subcommand_app, 'help base')
    assert out[0].startswith('Usage: base')
    assert out[1] == ''
    assert out[2] == 'Base command help'


def test_subcommand_help(subcommand_app) -> None:
    # foo has no aliases
    out, _err = run_cmd(subcommand_app, 'help base foo')
    assert out[0].startswith('Usage: base foo')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'

    # bar has aliases (usage should never show alias name)
    out, _err = run_cmd(subcommand_app, 'help base bar')
    assert out[0].startswith('Usage: base bar')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'

    out, _err = run_cmd(subcommand_app, 'help base bar_1')
    assert out[0].startswith('Usage: base bar')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'

    out, _err = run_cmd(subcommand_app, 'help base bar_2')
    assert out[0].startswith('Usage: base bar')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'

    # helpless has aliases and no help text (usage should never show alias name)
    out, _err = run_cmd(subcommand_app, 'help base helpless')
    assert out[0].startswith('Usage: base helpless')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'

    out, _err = run_cmd(subcommand_app, 'help base helpless_1')
    assert out[0].startswith('Usage: base helpless')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'

    out, _err = run_cmd(subcommand_app, 'help base helpless_2')
    assert out[0].startswith('Usage: base helpless')
    assert out[1] == ''
    assert out[2] == 'Positional Arguments:'


def test_subcommand_invalid_help(subcommand_app) -> None:
    out, _err = run_cmd(subcommand_app, 'help base baz')
    assert out[0].startswith('Usage: base')
