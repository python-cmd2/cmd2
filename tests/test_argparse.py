# coding=utf-8
# flake8: noqa E302
"""
Cmd2 testing for argument parsing
"""
import argparse
import pytest

import cmd2
from cmd2.utils import StdSim

from .conftest import run_cmd

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


class ArgparseApp(cmd2.Cmd):
    def __init__(self):
        self.maxrepeats = 3
        cmd2.Cmd.__init__(self)

    def namespace_provider(self) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.custom_stuff = "custom"
        return ns

    say_parser = argparse.ArgumentParser()
    say_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    say_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    say_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    say_parser.add_argument('words', nargs='+', help='words to say')

    @cmd2.with_argparser(say_parser)
    def do_say(self, args):
        """Repeat what you tell me to."""
        words = []
        for word in args.words:
            if word is None:
                word = ''
            if args.piglatin:
                word = '%s%say' % (word[1:], word[0])
            if args.shout:
                word = word.upper()
            words.append(word)
        repetitions = args.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(' '.join(words))
            self.stdout.write('\n')

    tag_parser = argparse.ArgumentParser(description='create a html tag')
    tag_parser.add_argument('tag', help='tag')
    tag_parser.add_argument('content', nargs='+', help='content to surround with tag')

    @cmd2.with_argparser(tag_parser, preserve_quotes=True)
    def do_tag(self, args):
        self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
        self.stdout.write('\n')

    @cmd2.with_argparser(argparse.ArgumentParser(), ns_provider=namespace_provider)
    def do_test_argparse_ns(self, args):
        self.stdout.write('{}'.format(args.custom_stuff))

    @cmd2.with_argument_list
    def do_arglist(self, arglist):
        if isinstance(arglist, list):
            self.stdout.write('True')
        else:
            self.stdout.write('False')

    @cmd2.with_argument_list(preserve_quotes=True)
    def do_preservelist(self, arglist):
        self.stdout.write('{}'.format(arglist))

    known_parser = argparse.ArgumentParser()
    known_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    known_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    known_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    @cmd2.with_argparser_and_unknown_args(known_parser)
    def do_speak(self, args, extra):
        """Repeat what you tell me to."""
        words = []
        for word in extra:
            if word is None:
                word = ''
            if args.piglatin:
                word = '%s%say' % (word[1:], word[0])
            if args.shout:
                word = word.upper()
            words.append(word)
        repetitions = args.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(' '.join(words))
            self.stdout.write('\n')

    @cmd2.with_argparser_and_unknown_args(argparse.ArgumentParser(), preserve_quotes=True)
    def do_test_argparse_with_list_quotes(self, args, extra):
        self.stdout.write('{}'.format(' '.join(extra)))

    @cmd2.with_argparser_and_unknown_args(argparse.ArgumentParser(), ns_provider=namespace_provider)
    def do_test_argparse_with_list_ns(self, args, extra):
        self.stdout.write('{}'.format(args.custom_stuff))


@pytest.fixture
def argparse_app():
    app = ArgparseApp()
    return app


def test_invalid_syntax(argparse_app):
    out, err = run_cmd(argparse_app, 'speak "')
    assert err[0] == "Invalid syntax: No closing quotation"

def test_argparse_basic_command(argparse_app):
    out, err = run_cmd(argparse_app, 'say hello')
    assert out == ['hello']

def test_argparse_remove_quotes(argparse_app):
    out, err = run_cmd(argparse_app, 'say "hello there"')
    assert out == ['hello there']

def test_argparse_preserve_quotes(argparse_app):
    out, err = run_cmd(argparse_app, 'tag mytag "hello"')
    assert out[0] == '<mytag>"hello"</mytag>'

def test_argparse_custom_namespace(argparse_app):
    out, err = run_cmd(argparse_app, 'test_argparse_ns')
    assert out[0] == 'custom'

def test_argparse_with_list(argparse_app):
    out, err = run_cmd(argparse_app, 'speak -s hello world!')
    assert out == ['HELLO WORLD!']

def test_argparse_with_list_remove_quotes(argparse_app):
    out, err = run_cmd(argparse_app, 'speak -s hello "world!"')
    assert out == ['HELLO WORLD!']

def test_argparse_with_list_preserve_quotes(argparse_app):
    out, err = run_cmd(argparse_app, 'test_argparse_with_list_quotes "hello" person')
    assert out[0] == '"hello" person'

def test_argparse_with_list_custom_namespace(argparse_app):
    out, err = run_cmd(argparse_app, 'test_argparse_with_list_ns')
    assert out[0] == 'custom'

def test_argparse_with_list_and_empty_doc(argparse_app):
    out, err = run_cmd(argparse_app, 'speak -s hello world!')
    assert out == ['HELLO WORLD!']

def test_argparser_correct_args_with_quotes_and_midline_options(argparse_app):
    out, err = run_cmd(argparse_app, "speak 'This  is a' -s test of the emergency broadcast system!")
    assert out == ['THIS  IS A TEST OF THE EMERGENCY BROADCAST SYSTEM!']

def test_argparse_quoted_arguments_multiple(argparse_app):
    out, err = run_cmd(argparse_app, 'say "hello  there" "rick & morty"')
    assert out == ['hello  there rick & morty']

def test_argparse_help_docstring(argparse_app):
    out, err = run_cmd(argparse_app, 'help say')
    assert out[0].startswith('usage: say')
    assert out[1] == ''
    assert out[2] == 'Repeat what you tell me to.'

def test_argparse_help_description(argparse_app):
    out, err = run_cmd(argparse_app, 'help tag')
    assert out[0].startswith('usage: tag')
    assert out[1] == ''
    assert out[2] == 'create a html tag'

def test_argparse_prog(argparse_app):
    out, err = run_cmd(argparse_app, 'help tag')
    progname = out[0].split(' ')[1]
    assert progname == 'tag'

def test_arglist(argparse_app):
    out, err = run_cmd(argparse_app, 'arglist "we  should" get these')
    assert out[0] == 'True'

def test_preservelist(argparse_app):
    out, err = run_cmd(argparse_app, 'preservelist foo "bar baz"')
    assert out[0] == "['foo', '\"bar baz\"']"


class SubcommandApp(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""

    def __init__(self):
        cmd2.Cmd.__init__(self)

    # subcommand functions for the base command
    def base_foo(self, args):
        """foo subcommand of base command"""
        self.poutput(args.x * args.y)

    def base_bar(self, args):
        """bar subcommand of base command"""
        self.poutput('((%s))' % args.z)

    # create the top-level parser for the base command
    base_parser = argparse.ArgumentParser()
    base_subparsers = base_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.set_defaults(func=base_foo)

    # create the parser for the "bar" subcommand
    parser_bar = base_subparsers.add_parser('bar', help='bar help')
    parser_bar.add_argument('z', help='string')
    parser_bar.set_defaults(func=base_bar)

    @cmd2.with_argparser(base_parser)
    def do_base(self, args):
        """Base command help"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('base')

@pytest.fixture
def subcommand_app():
    app = SubcommandApp()
    return app


def test_subcommand_foo(subcommand_app):
    out, err = run_cmd(subcommand_app, 'base foo -x2 5.0')
    assert out == ['10.0']


def test_subcommand_bar(subcommand_app):
    out, err = run_cmd(subcommand_app, 'base bar baz')
    assert out == ['((baz))']

def test_subcommand_invalid(subcommand_app):
    out, err = run_cmd(subcommand_app, 'base baz')
    assert err[0].startswith('usage: base')
    assert err[1].startswith("base: error: invalid choice: 'baz'")

def test_subcommand_base_help(subcommand_app):
    out, err = run_cmd(subcommand_app, 'help base')
    assert out[0].startswith('usage: base')
    assert out[1] == ''
    assert out[2] == 'Base command help'

def test_subcommand_help(subcommand_app):
    out, err = run_cmd(subcommand_app, 'help base foo')
    assert out[0].startswith('usage: base foo')
    assert out[1] == ''
    assert out[2] == 'positional arguments:'


def test_subcommand_invalid_help(subcommand_app):
    out, err = run_cmd(subcommand_app, 'help base baz')
    assert out[0].startswith('usage: base')
