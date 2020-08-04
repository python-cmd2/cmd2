#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How arguments and options get parsed and passed to commands
    2) How to change what syntax gets parsed as a comment and stripped from the arguments

This is intended to serve as a live demonstration so that developers can
experiment with and understand how command and argument parsing work.

It also serves as an example of how to create shortcuts.
"""
import argparse

import cmd2


class ArgumentAndOptionPrinter(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        # Create command shortcuts which are typically 1 character abbreviations which can be used in place of a command
        shortcuts = dict(cmd2.DEFAULT_SHORTCUTS)
        shortcuts.update({'$': 'aprint', '%': 'oprint'})
        super().__init__(shortcuts=shortcuts)

    def do_aprint(self, statement):
        """Print the argument string this basic command is called with."""
        self.poutput('aprint was called with argument: {!r}'.format(statement))
        self.poutput('statement.raw = {!r}'.format(statement.raw))
        self.poutput('statement.argv = {!r}'.format(statement.argv))
        self.poutput('statement.command = {!r}'.format(statement.command))

    @cmd2.with_argument_list
    def do_lprint(self, arglist):
        """Print the argument list this basic command is called with."""
        self.poutput('lprint was called with the following list of arguments: {!r}'.format(arglist))

    @cmd2.with_argument_list(preserve_quotes=True)
    def do_rprint(self, arglist):
        """Print the argument list this basic command is called with (with quotes preserved)."""
        self.poutput('rprint was called with the following list of arguments: {!r}'.format(arglist))

    oprint_parser = argparse.ArgumentParser()
    oprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    oprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    oprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    oprint_parser.add_argument('words', nargs='+', help='words to print')

    @cmd2.with_argparser(oprint_parser)
    def do_oprint(self, args):
        """Print the options and argument list this options command was called with."""
        self.poutput('oprint was called with the following\n\toptions: {!r}'.format(args))

    pprint_parser = argparse.ArgumentParser()
    pprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    pprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    pprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')

    @cmd2.with_argparser(pprint_parser, with_unknown_args=True)
    def do_pprint(self, args, unknown):
        """Print the options and argument list this options command was called with."""
        self.poutput('oprint was called with the following\n\toptions: {!r}\n\targuments: {}'.format(args, unknown))


if __name__ == '__main__':
    import sys
    app = ArgumentAndOptionPrinter()
    sys.exit(app.cmdloop())
