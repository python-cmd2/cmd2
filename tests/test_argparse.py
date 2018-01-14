# coding=utf-8
"""
Cmd2 testing for argument parsing
"""
import re
import argparse
import pytest

import cmd2
from conftest import run_cmd, StdOut

class ArgparseApp(cmd2.Cmd):
    def __init__(self):
        self.maxrepeats = 3
        cmd2.Cmd.__init__(self)

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    argparser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    argparser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    argparser.add_argument('words', nargs='+', help='words to say')
    @cmd2.with_argument_parser(argparser)
    def do_say(self, arglist, args=None):
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

    argparser = argparse.ArgumentParser(description='create a html tag')
    argparser.add_argument('tag', nargs=1, help='tag')
    argparser.add_argument('content', nargs='+', help='content to surround with tag')
    @cmd2.with_argument_parser(argparser)
    def do_tag(self, arglist, args=None):
        self.stdout.write('<{0}>{1}</{0}>'.format(args.tag[0], ' '.join(args.content)))
        self.stdout.write('\n')

    argparser = argparse.ArgumentParser()
    argparser.add_argument('args', nargs='*')
    @cmd2.with_argument_parser(argparser)
    def do_compare(self, arglist, args=None):
        cmdline_str = re.sub('\s+', ' ', ' '.join(arglist))
        args_str = re.sub('\s+', ' ', ' '.join(args.args))
        if cmdline_str == args_str:
            self.stdout.write('True')
        else:
            self.stdout.write('False')

    argparser = argparse.ArgumentParser()
    argparser.add_argument('args', nargs='*')
    @cmd2.with_argument_parser(argparser)
    def do_argparse_arglist(self, arglist, args=None):
        if isinstance(arglist, list):
            self.stdout.write('True')
        else:
            self.stdout.write('False')


    argparser = argparse.ArgumentParser()
    argparser.add_argument('args', nargs='*')
    @cmd2.with_argument_list
    @cmd2.with_argument_parser(argparser)
    def do_arglistandargparser(self, arglist, args=None):
        if isinstance(arglist, list):
            self.stdout.write(' '.join(arglist))
        else:
            self.stdout.write('False')

    @cmd2.with_argument_list
    def do_arglist(self, arglist):
        if isinstance(arglist, list):
            self.stdout.write('True')
        else:
            self.stdout.write('False')

    @cmd2.with_argument_list
    @cmd2.with_argument_list
    def do_arglisttwice(self, arglist):
        if isinstance(arglist, list):
            self.stdout.write(' '.join(arglist))
        else:
            self.stdout.write('False')


class ArglistApp(cmd2.Cmd):
    def __init__(self):
        self.use_argument_list = True
        cmd2.Cmd.__init__(self)

    def do_arglist(self, arglist):
        """Print true if the arglist parameter is passed as a list."""
        if isinstance(arglist, list):
            self.stdout.write('True')
        else:
            self.stdout.write('False')

    @cmd2.with_argument_list
    def do_arglistwithdecorator(self, arglist):
        self.stdout.write(' '.join(arglist))
        

@pytest.fixture
def argparse_app():
    app = ArgparseApp()
    app.stdout = StdOut()
    return app

@pytest.fixture
def arglist_app():
    app = ArglistApp()
    app.stdout = StdOut()
    return app

def test_argparse_basic_command(argparse_app):
    out = run_cmd(argparse_app, 'say hello')
    assert out == ['hello']

def test_argparse_quoted_arguments(argparse_app):
    argparse_app.POSIX = False
    argparse_app.STRIP_QUOTES_FOR_NON_POSIX = True
    out = run_cmd(argparse_app, 'say "hello there"')
    assert out == ['hello there']

def test_argparse_quoted_arguments_multiple(argparse_app):
    argparse_app.POSIX = False
    argparse_app.STRIP_QUOTES_FOR_NON_POSIX = True
    out = run_cmd(argparse_app, 'say "hello  there" "rick & morty"')
    assert out == ['hello  there rick & morty']

def test_argparse_quoted_arguments_posix(argparse_app):
    argparse_app.POSIX = True
    out = run_cmd(argparse_app, 'tag strong this should be loud')
    assert out == ['<strong>this should be loud</strong>']

def test_argparse_quoted_arguments_posix_multiple(argparse_app):
    argparse_app.POSIX = True
    out = run_cmd(argparse_app, 'tag strong this "should  be" loud')
    assert out == ['<strong>this should  be loud</strong>']

def test_argparse_help_docstring(argparse_app):
    out = run_cmd(argparse_app, 'help say')
    assert out[0] == 'Repeat what you tell me to.'

def test_argparse_help_description(argparse_app):
    out = run_cmd(argparse_app, 'help tag')
    assert out[2] == 'create a html tag'

def test_argparse_prog(argparse_app):
    out = run_cmd(argparse_app, 'help tag')
    progname = out[0].split(' ')[1]
    assert progname == 'tag'

def test_argparse_cmdline(argparse_app):
    out = run_cmd(argparse_app, 'compare this is a test')
    assert out[0] == 'True'

def test_argparse_arglist(argparse_app):
    out = run_cmd(argparse_app, 'argparse_arglist "some   arguments" and some more')
    assert out[0] == 'True'

def test_arglist(argparse_app):
    out = run_cmd(argparse_app, 'arglist "we  should" get these')
    assert out[0] == 'True'

def test_arglist_decorator_twice(argparse_app):
    out = run_cmd(argparse_app, 'arglisttwice "we  should" get these')
    assert out[0] == 'we  should get these'

def test_arglist_and_argparser(argparse_app):
    out = run_cmd(argparse_app, 'arglistandargparser some "quoted   words"')
    assert out[0] == 'some quoted   words'

def test_use_argument_list(arglist_app):
    out = run_cmd(arglist_app, 'arglist "we  should" get these in a list, not a string')
    assert out[0] == 'True'

def test_arglist_attribute_and_decorator(arglist_app):
    out = run_cmd(arglist_app, 'arglistwithdecorator "we  should" get these')
    assert out[0] == 'we  should get these'

#def test_arglist_help(arglist_app):
#    out = run_cmd(arglist_app, 'help arglist')
#    assert out[0] == 'True'
