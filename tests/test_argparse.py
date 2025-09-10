"""Cmd2 testing for argument parsing"""

import argparse

import pytest

import cmd2

from .conftest import (
    run_cmd,
)


class ArgparseApp(cmd2.Cmd):
    def __init__(self) -> None:
        self.maxrepeats = 3
        cmd2.Cmd.__init__(self)

    def namespace_provider(self) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.custom_stuff = "custom"
        return ns

    @staticmethod
    def _say_parser_builder() -> cmd2.Cmd2ArgumentParser:
        say_parser = cmd2.Cmd2ArgumentParser()
        say_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
        say_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
        say_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
        say_parser.add_argument('words', nargs='+', help='words to say')
        return say_parser

    @cmd2.with_argparser(_say_parser_builder)
    def do_say(self, args, *, keyword_arg: str | None = None) -> None:
        """Repeat what you tell me to.

        :param args: argparse namespace
        :param keyword_arg: Optional keyword arguments
        """
        words = []
        for word in args.words:
            modified_word = word
            if word is None:
                modified_word = ''
            if args.piglatin:
                modified_word = f'{word[1:]}{word[0]}ay'
            if args.shout:
                modified_word = word.upper()
            words.append(modified_word)
        repetitions = args.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(' '.join(words))
            self.stdout.write('\n')

        if keyword_arg is not None:
            print(keyword_arg)

    tag_parser = cmd2.Cmd2ArgumentParser(description='create a html tag')
    tag_parser.add_argument('tag', help='tag')
    tag_parser.add_argument('content', nargs='+', help='content to surround with tag')

    @cmd2.with_argparser(tag_parser, preserve_quotes=True)
    def do_tag(self, args) -> None:
        self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
        self.stdout.write('\n')

    @cmd2.with_argparser(cmd2.Cmd2ArgumentParser(), ns_provider=namespace_provider)
    def do_test_argparse_ns(self, args) -> None:
        self.stdout.write(f'{args.custom_stuff}')

    @cmd2.with_argument_list
    def do_arglist(self, arglist, *, keyword_arg: str | None = None) -> None:
        if isinstance(arglist, list):
            self.stdout.write('True')
        else:
            self.stdout.write('False')

        if keyword_arg is not None:
            print(keyword_arg)

    @cmd2.with_argument_list(preserve_quotes=True)
    def do_preservelist(self, arglist) -> None:
        self.stdout.write(f'{arglist}')

    @classmethod
    def _speak_parser_builder(cls) -> cmd2.Cmd2ArgumentParser:
        known_parser = cmd2.Cmd2ArgumentParser()
        known_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
        known_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
        known_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
        return known_parser

    @cmd2.with_argparser(_speak_parser_builder, with_unknown_args=True)
    def do_speak(self, args, extra, *, keyword_arg: str | None = None) -> None:
        """Repeat what you tell me to."""
        words = []
        for word in extra:
            modified_word = word
            if word is None:
                modified_word = ''
            if args.piglatin:
                modified_word = f'{word[1:]}{word[0]}ay'
            if args.shout:
                modified_word = word.upper()
            words.append(modified_word)
        repetitions = args.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(' '.join(words))
            self.stdout.write('\n')

        if keyword_arg is not None:
            print(keyword_arg)

    @cmd2.with_argparser(cmd2.Cmd2ArgumentParser(), preserve_quotes=True, with_unknown_args=True)
    def do_test_argparse_with_list_quotes(self, args, extra) -> None:
        self.stdout.write('{}'.format(' '.join(extra)))

    @cmd2.with_argparser(cmd2.Cmd2ArgumentParser(), ns_provider=namespace_provider, with_unknown_args=True)
    def do_test_argparse_with_list_ns(self, args, extra) -> None:
        self.stdout.write(f'{args.custom_stuff}')


@pytest.fixture
def argparse_app():
    return ArgparseApp()


def test_invalid_syntax(argparse_app) -> None:
    _out, err = run_cmd(argparse_app, 'speak "')
    assert err[0] == "Invalid syntax: No closing quotation"


def test_argparse_basic_command(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'say hello')
    assert out == ['hello']


def test_argparse_remove_quotes(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'say "hello there"')
    assert out == ['hello there']


def test_argparse_with_no_args(argparse_app) -> None:
    """Make sure we receive TypeError when calling argparse-based function with no args"""
    with pytest.raises(TypeError) as excinfo:
        argparse_app.do_say()
    assert 'Expected arguments' in str(excinfo.value)


def test_argparser_kwargs(argparse_app, capsys) -> None:
    """Test with_argparser wrapper passes through kwargs to command function"""
    argparse_app.do_say('word', keyword_arg="foo")
    out, _err = capsys.readouterr()
    assert out == "foo\n"


def test_argparse_preserve_quotes(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'tag mytag "hello"')
    assert out[0] == '<mytag>"hello"</mytag>'


def test_argparse_custom_namespace(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'test_argparse_ns')
    assert out[0] == 'custom'


def test_argparse_with_list(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'speak -s hello world!')
    assert out == ['HELLO WORLD!']


def test_argparse_with_list_remove_quotes(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'speak -s hello "world!"')
    assert out == ['HELLO WORLD!']


def test_argparse_with_list_preserve_quotes(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'test_argparse_with_list_quotes "hello" person')
    assert out[0] == '"hello" person'


def test_argparse_with_list_custom_namespace(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'test_argparse_with_list_ns')
    assert out[0] == 'custom'


def test_argparse_with_list_and_empty_doc(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'speak -s hello world!')
    assert out == ['HELLO WORLD!']


def test_argparser_correct_args_with_quotes_and_midline_options(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, "speak 'This  is a' -s test of the emergency broadcast system!")
    assert out == ['THIS  IS A TEST OF THE EMERGENCY BROADCAST SYSTEM!']


def test_argparser_and_unknown_args_kwargs(argparse_app, capsys) -> None:
    """Test with_argparser wrapper passing through kwargs to command function"""
    argparse_app.do_speak('', keyword_arg="foo")
    out, _err = capsys.readouterr()
    assert out == "foo\n"


def test_argparse_quoted_arguments_multiple(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'say "hello  there" "rick & morty"')
    assert out == ['hello  there rick & morty']


def test_argparse_help_docstring(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'help say')
    assert out[0].startswith('Usage: say')
    assert out[1] == ''
    assert out[2] == 'Repeat what you tell me to.'
    for line in out:
        assert not line.startswith(':')


def test_argparse_help_description(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'help tag')
    assert out[0].startswith('Usage: tag')
    assert out[1] == ''
    assert out[2] == 'create a html tag'


def test_argparse_prog(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'help tag')
    progname = out[0].split(' ')[1]
    assert progname == 'tag'


def test_arglist(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'arglist "we  should" get these')
    assert out[0] == 'True'


def test_arglist_kwargs(argparse_app, capsys) -> None:
    """Test with_argument_list wrapper passes through kwargs to command function"""
    argparse_app.do_arglist('arg', keyword_arg="foo")
    out, _err = capsys.readouterr()
    assert out == "foo\n"


def test_preservelist(argparse_app) -> None:
    out, _err = run_cmd(argparse_app, 'preservelist foo "bar baz"')
    assert out[0] == "['foo', '\"bar baz\"']"


def test_invalid_parser_builder(argparse_app):
    parser_builder = None
    with pytest.raises(TypeError):
        argparse_app._build_parser(argparse_app, parser_builder, "fake_prog")


def _build_has_subcmd_parser() -> cmd2.Cmd2ArgumentParser:
    has_subcmds_parser = cmd2.Cmd2ArgumentParser(description="Tests as_subcmd_to decorator")
    has_subcmds_parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND', required=True)
    return has_subcmds_parser


class SubcommandApp(cmd2.Cmd):
    """Example cmd2 application where we a base command which has a couple subcommands."""

    # subcommand functions for the base command
    def base_foo(self, args) -> None:
        """Foo subcommand of base command"""
        self.poutput(args.x * args.y)

    def base_bar(self, args) -> None:
        """Bar subcommand of base command"""
        self.poutput(f'(({args.z}))')

    def base_helpless(self, args) -> None:
        """Helpless subcommand of base command"""
        self.poutput(f'(({args.z}))')

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

    # Add subcommands using as_subcommand_to decorator
    @cmd2.with_argparser(_build_has_subcmd_parser)
    def do_test_subcmd_decorator(self, args: argparse.Namespace) -> None:
        handler = args.cmd2_handler.get()
        handler(args)

    subcmd_parser = cmd2.Cmd2ArgumentParser(description="A subcommand")

    @cmd2.as_subcommand_to('test_subcmd_decorator', 'subcmd', subcmd_parser, help=subcmd_parser.description.lower())
    def subcmd_func(self, args: argparse.Namespace) -> None:
        # Make sure printing the Namespace works. The way we originally added cmd2_handler to it resulted in a RecursionError.
        self.poutput(args)

    helpless_subcmd_parser = cmd2.Cmd2ArgumentParser(add_help=False, description="A subcommand with no help")

    @cmd2.as_subcommand_to(
        'test_subcmd_decorator', 'helpless_subcmd', helpless_subcmd_parser, help=helpless_subcmd_parser.description.lower()
    )
    def helpless_subcmd_func(self, args: argparse.Namespace) -> None:
        # Make sure vars(Namespace) works. The way we originally added cmd2_handler to it resulted in a RecursionError.
        self.poutput(vars(args))


@pytest.fixture
def subcommand_app():
    return SubcommandApp()


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


def test_add_another_subcommand(subcommand_app) -> None:
    """This tests makes sure set_parser_prog() sets _prog_prefix on every _SubParsersAction so that all future calls
    to add_parser() write the correct prog value to the parser being added.
    """
    base_parser = subcommand_app._command_parsers.get(subcommand_app.do_base)
    for sub_action in base_parser._actions:
        if isinstance(sub_action, argparse._SubParsersAction):
            new_parser = sub_action.add_parser('new_sub', help='stuff')
            break

    assert new_parser.prog == "base new_sub"


def test_subcmd_decorator(subcommand_app) -> None:
    # Test subcommand that has help option
    out, err = run_cmd(subcommand_app, 'test_subcmd_decorator subcmd')
    assert out[0].startswith('Namespace(')

    out, err = run_cmd(subcommand_app, 'help test_subcmd_decorator subcmd')
    assert out[0] == 'Usage: test_subcmd_decorator subcmd [-h]'

    out, err = run_cmd(subcommand_app, 'test_subcmd_decorator subcmd -h')
    assert out[0] == 'Usage: test_subcmd_decorator subcmd [-h]'

    # Test subcommand that has no help option
    out, err = run_cmd(subcommand_app, 'test_subcmd_decorator helpless_subcmd')
    assert "'subcommand': 'helpless_subcmd'" in out[1]

    out, err = run_cmd(subcommand_app, 'help test_subcmd_decorator helpless_subcmd')
    assert out[0] == 'Usage: test_subcmd_decorator helpless_subcmd'
    assert not err

    out, err = run_cmd(subcommand_app, 'test_subcmd_decorator helpless_subcmd -h')
    assert not out
    assert err[0] == 'Usage: test_subcmd_decorator [-h] SUBCOMMAND ...'
    assert err[1] == 'Error: unrecognized arguments: -h'


def test_unittest_mock() -> None:
    from unittest import (
        mock,
    )

    from cmd2 import (
        CommandSetRegistrationError,
    )

    with mock.patch.object(ArgparseApp, 'namespace_provider'), pytest.raises(CommandSetRegistrationError):
        ArgparseApp()

    with mock.patch.object(ArgparseApp, 'namespace_provider', spec=True):
        ArgparseApp()

    with mock.patch.object(ArgparseApp, 'namespace_provider', spec_set=True):
        ArgparseApp()

    with mock.patch.object(ArgparseApp, 'namespace_provider', autospec=True):
        ArgparseApp()


def test_pytest_mock_invalid(mocker) -> None:
    from cmd2 import (
        CommandSetRegistrationError,
    )

    mocker.patch.object(ArgparseApp, 'namespace_provider')
    with pytest.raises(CommandSetRegistrationError):
        ArgparseApp()


@pytest.mark.parametrize(
    'spec_param',
    [
        {'spec': True},
        {'spec_set': True},
        {'autospec': True},
    ],
)
def test_pytest_mock_valid(mocker, spec_param) -> None:
    mocker.patch.object(ArgparseApp, 'namespace_provider', **spec_param)
    ArgparseApp()
