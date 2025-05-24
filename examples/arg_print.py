#!/usr/bin/env python
"""A simple example demonstrating the following:
    1) How arguments and options get parsed and passed to commands
    2) How to change what syntax gets parsed as a comment and stripped from the arguments.

This is intended to serve as a live demonstration so that developers can
experiment with and understand how command and argument parsing work.

It also serves as an example of how to create shortcuts.
"""

import cmd2


class ArgumentAndOptionPrinter(cmd2.Cmd):
    """Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self) -> None:
        # Create command shortcuts which are typically 1 character abbreviations which can be used in place of a command
        shortcuts = dict(cmd2.DEFAULT_SHORTCUTS)
        shortcuts.update({'$': 'aprint', '%': 'oprint'})
        super().__init__(shortcuts=shortcuts)

    def do_aprint(self, statement) -> None:
        """Print the argument string this basic command is called with."""
        self.poutput(f'aprint was called with argument: {statement!r}')
        self.poutput(f'statement.raw = {statement.raw!r}')
        self.poutput(f'statement.argv = {statement.argv!r}')
        self.poutput(f'statement.command = {statement.command!r}')

    @cmd2.with_argument_list
    def do_lprint(self, arglist) -> None:
        """Print the argument list this basic command is called with."""
        self.poutput(f'lprint was called with the following list of arguments: {arglist!r}')

    @cmd2.with_argument_list(preserve_quotes=True)
    def do_rprint(self, arglist) -> None:
        """Print the argument list this basic command is called with (with quotes preserved)."""
        self.poutput(f'rprint was called with the following list of arguments: {arglist!r}')

    oprint_parser = cmd2.Cmd2ArgumentParser()
    oprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    oprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    oprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    oprint_parser.add_argument('words', nargs='+', help='words to print')

    @cmd2.with_argparser(oprint_parser)
    def do_oprint(self, args) -> None:
        """Print the options and argument list this options command was called with."""
        self.poutput(f'oprint was called with the following\n\toptions: {args!r}')

    pprint_parser = cmd2.Cmd2ArgumentParser()
    pprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    pprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    pprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')

    @cmd2.with_argparser(pprint_parser, with_unknown_args=True)
    def do_pprint(self, args, unknown) -> None:
        """Print the options and argument list this options command was called with."""
        self.poutput(f'oprint was called with the following\n\toptions: {args!r}\n\targuments: {unknown}')


if __name__ == '__main__':
    import sys

    app = ArgumentAndOptionPrinter()
    sys.exit(app.cmdloop())
