# coding=utf-8
"""
Cmd2 testing for argument parsing
"""
import argparse
import pytest

import cmd2
from conftest import run_cmd, StdOut

class ArgparseApp(cmd2.Cmd):
    def __init__(self):
        self.maxrepeats = 3
        cmd2.Cmd.__init__(self)

    argparser = argparse.ArgumentParser(
      prog='say',
      description='Repeats what you tell me to'
    )
    argparser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    argparser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    argparser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    argparser.add_argument('words', nargs='+', help='words to say')
    @cmd2.with_argument_parser(argparser)
    def do_say(self, cmdline, args=None):
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

    argparser = argparse.ArgumentParser(
      prog='tag',
      description='create an html tag, the first argument is the tag, the rest is the contents'
    )
    argparser.add_argument('tag', nargs=1, help='tag')
    argparser.add_argument('content', nargs='+', help='content to surround with tag')
    @cmd2.with_argument_parser(argparser)
    def do_tag(self, cmdline, args=None):
        self.stdout.write('<{0}>{1}</{0}>'.format(args.tag[0], ' '.join(args.content)))
        self.stdout.write('\n')


@pytest.fixture
def argparse_app():
    app = ArgparseApp()
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
