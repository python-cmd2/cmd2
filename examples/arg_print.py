#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How arguments and options get parsed and passed to commands
    2) How to change what syntax get parsed as a comment and stripped from
       the arguments

This is intended to serve as a live demonstration so that developers can
experiment with and understand how command and argument parsing work.

It also serves as an example of how to create command aliases (shortcuts).
"""
import argparse

import cmd2

class ArgumentAndOptionPrinter(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        # Create command aliases which are shorter
        self.shortcuts.update({'$': 'aprint', '%': 'oprint'})

        # Make sure to call this super class __init__ *after* setting and/or updating shortcuts
        super().__init__()
        # NOTE: It is critical that the super class __init__ method be called AFTER updating certain parameters which
        # are not settable at runtime.  This includes the shortcuts, multiline_commands, etc.

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
    @cmd2.with_argparser_and_unknown_args(pprint_parser)
    def do_pprint(self, args, unknown):
        """Print the options and argument list this options command was called with."""
        self.poutput('oprint was called with the following\n\toptions: {!r}\n\targuments: {}'.format(args, unknown))


if __name__ == '__main__':
    app = ArgumentAndOptionPrinter()
    app.cmdloop()
