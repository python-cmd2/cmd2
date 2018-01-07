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
    argparser.add_argument('word', nargs='?', help='word to say')
    @cmd2.with_argument_parser(argparser)
    def do_say(self, cmdline, args=None):
        word = args.word
        if word is None:
            word = ''
        if args.piglatin:
            word = '%s%say' % (word[1:], word[0])
        if args.shout:
            word = word.upper()
        repetitions = args.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(word)
            self.stdout.write('\n')

@pytest.fixture
def argparse_app():
    app = ArgparseApp()
    app.stdout = StdOut()
    return app

def test_argparse_basic_command(argparse_app):
    out = run_cmd(argparse_app, 'say hello')
    assert out == ['hello']

#def test_argparse_quoted_arguments(argparse_app):
#    out = run_cmd(argparse_app, 'say "hello there"')
#    assert out == ['hello there']

#def test_pargparse_quoted_arguments_too_many(argparse_app):
#    out = run_cmd(argparse_app, 'say "hello there" morty')
#    assert out == ['hello there morty']
