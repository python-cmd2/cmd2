#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How arguments and options get parsed and passed to commands
    2) How to change what syntax get parsed as a comment and stripped from the arguments

This is intended to serve as a live demonstration so that developers can experiment with and understand how command
and argument parsing is intended to work.

It also serves as an example of how to create command aliases (shortcuts).
"""
import pyparsing
import cmd2
from cmd2 import options
from optparse import make_option


class ArgumentAndOptionPrinter(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        # Uncomment this line to disable Python-style comments but still allow C-style comments
        # self.commentGrammars = pyparsing.Or([pyparsing.cStyleComment])

        # Create command aliases which are shorter
        self.shortcuts.update({'ap': 'aprint', 'op': 'oprint'})

        # Make sure to call this super class __init__ *after* setting commentGrammars and/or updating shortcuts
        cmd2.Cmd.__init__(self)
        # NOTE: It is critical that the super class __init__ method be called AFTER updating certain parameters which
        # are not settable at runtime.  This includes the commentGrammars, shortcuts, multilineCommands, etc.

    def do_aprint(self, arg):
        """Print the argument string this basic command is called with."""
        print('aprint was called with argument: {!r}'.format(arg))

    @options([make_option('-p', '--piglatin', action="store_true", help="atinLay"),
              make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
              make_option('-r', '--repeat', type="int", help="output [n] times")], arg_desc='positional_arg_string')
    def do_oprint(self, arg, opts=None):
        """Print the options and argument list this options command was called with."""
        print('oprint was called with the following\n\toptions: {!r}\n\targuments: {!r}'.format(opts, arg))


if __name__ == '__main__':
    app = ArgumentAndOptionPrinter()
    app.cmdloop()
