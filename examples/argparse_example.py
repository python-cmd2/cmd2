#!/usr/bin/env python3
"""A comprehensive example demonstrating various aspects of using `argparse` for command argument processing.

Demonstrates basic usage of the `cmd2.with_argparser` decorator for passing a `cmd2.Cmd2ArgumentParser` to a `do_*` command
method. The `fsize` and `pow` commands demonstrate various different types of arguments, actions, choices, and completers that
can be used.

The `print_args` and `print_unknown` commands display how argparse arguments are passed to commands in the cases that unknown
arguments are not captured and are captured, respectively.

The `base` and `alternate` commands show an easy way for a single command to have many subcommands, each of which take
different arguments and provides separate contextual help.

Lastly, this example shows how you can also use `argparse` to parse command-line arguments when launching a cmd2 application.
"""

import argparse
import os

import cmd2
from cmd2.string_utils import stylize

# Command categories
ARGPARSE_USAGE = 'Argparse Basic Usage'
ARGPARSE_PRINTING = 'Argparse Printing'
ARGPARSE_SUBCOMMANDS = 'Argparse Subcommands'


class ArgparsingApp(cmd2.Cmd):
    def __init__(self, color: str) -> None:
        """Cmd2 application for demonstrating the use of argparse for command argument parsing."""
        super().__init__(include_ipy=True)
        self.intro = stylize(
            'cmd2 has awesome decorators to make it easy to use Argparse to parse command arguments', style=color
        )

    ## ------ Basic examples of using argparse for command argument parsing -----

    # do_fsize parser
    fsize_parser = cmd2.Cmd2ArgumentParser(description='Obtain the size of a file')
    fsize_parser.add_argument('-c', '--comma', action='store_true', help='add comma for thousands separator')
    fsize_parser.add_argument('-u', '--unit', choices=['MB', 'KB'], help='unit to display size in')
    fsize_parser.add_argument('file_path', help='path of file', completer=cmd2.Cmd.path_complete)

    @cmd2.with_argparser(fsize_parser)
    @cmd2.with_category(ARGPARSE_USAGE)
    def do_fsize(self, args: argparse.Namespace) -> None:
        """Obtain the size of a file."""
        expanded_path = os.path.expanduser(args.file_path)

        try:
            size = os.path.getsize(expanded_path)
        except OSError as ex:
            self.perror(f"Error retrieving size: {ex}")
            return

        if args.unit == 'KB':
            size //= 1024
        elif args.unit == 'MB':
            size //= 1024 * 1024
        else:
            args.unit = 'bytes'
        size = round(size, 2)

        size_str = f'{size:,}' if args.comma else f'{size}'
        self.poutput(f'{size_str} {args.unit}')

    # do_pow parser
    pow_parser = cmd2.Cmd2ArgumentParser()
    pow_parser.add_argument('base', type=int)
    pow_parser.add_argument('exponent', type=int, choices=range(-5, 6))

    @cmd2.with_argparser(pow_parser)
    @cmd2.with_category(ARGPARSE_USAGE)
    def do_pow(self, args: argparse.Namespace) -> None:
        """Raise an integer to a small integer exponent, either positive or negative.

        :param args: argparse arguments
        """
        self.poutput(f'{args.base} ** {args.exponent} == {args.base**args.exponent}')

    ## ------ Examples displaying how argparse arguments are passed to commands by printing them out -----

    argprint_parser = cmd2.Cmd2ArgumentParser()
    argprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    argprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    argprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    argprint_parser.add_argument('words', nargs='+', help='words to print')

    @cmd2.with_argparser(argprint_parser)
    @cmd2.with_category(ARGPARSE_PRINTING)
    def do_print_args(self, args: argparse.Namespace) -> None:
        """Print the arpgarse argument list this command was called with."""
        self.poutput(f'print_args was called with the following\n\targuments: {args!r}')

    unknownprint_parser = cmd2.Cmd2ArgumentParser()
    unknownprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    unknownprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    unknownprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')

    @cmd2.with_argparser(unknownprint_parser, with_unknown_args=True)
    @cmd2.with_category(ARGPARSE_PRINTING)
    def do_print_unknown(self, args: argparse.Namespace, unknown: list[str]) -> None:
        """Print the arpgarse argument list this command was called with, including unknown arguments."""
        self.poutput(f'print_unknown was called with the following arguments\n\tknown: {args!r}\n\tunknown: {unknown}')

    ## ------ Examples demonstrating how to use argparse subcommands -----

    # create the top-level parser for the base command
    calculate_parser = cmd2.Cmd2ArgumentParser(description="Perform simple mathematical calculations.")
    calculate_subparsers = calculate_parser.add_subparsers(title='operation', help='Available operations', required=True)

    # create the parser for the "add" subcommand
    add_description = "Add two numbers"
    add_parser = cmd2.Cmd2ArgumentParser("add", description=add_description)
    add_parser.add_argument('num1', type=int, help='The first number')
    add_parser.add_argument('num2', type=int, help='The second number')

    # create the parser for the "add" subcommand
    subtract_description = "Subtract two numbers"
    subtract_parser = cmd2.Cmd2ArgumentParser("subtract", description=subtract_description)
    subtract_parser.add_argument('num1', type=int, help='The first number')
    subtract_parser.add_argument('num2', type=int, help='The second number')

    # subcommand functions for the calculate command
    @cmd2.as_subcommand_to('calculate', 'add', add_parser, help=add_description.lower())
    def add(self, args: argparse.Namespace) -> None:
        """add subcommand of calculate command."""
        result = args.num1 + args.num2
        self.poutput(f"{args.num1} + {args.num2} = {result}")

    @cmd2.as_subcommand_to('calculate', 'subtract', subtract_parser, help=subtract_description.lower())
    def subtract(self, args: argparse.Namespace) -> None:
        """subtract subcommand of calculate command."""
        result = args.num1 - args.num2
        self.poutput(f"{args.num1} - {args.num2} = {result}")

    @cmd2.with_argparser(calculate_parser)
    @cmd2.with_category(ARGPARSE_SUBCOMMANDS)
    def do_calculate(self, args: argparse.Namespace) -> None:
        """Calculate a simple mathematical operation on two integers."""
        handler = args.cmd2_handler.get()
        handler(args)


if __name__ == '__main__':
    import sys

    from cmd2.colors import Color

    # You can do your custom Argparse parsing here to meet your application's needs
    parser = cmd2.Cmd2ArgumentParser(description='Process the arguments however you like.')

    # Add an argument which we will pass to the app to change some behavior
    parser.add_argument(
        '-c',
        '--color',
        choices=[Color.RED, Color.ORANGE1, Color.YELLOW, Color.GREEN, Color.BLUE, Color.PURPLE, Color.VIOLET, Color.WHITE],
        help='Color of intro text',
    )

    # Parse the arguments
    args, unknown_args = parser.parse_known_args()

    color = Color.WHITE
    if args.color:
        color = args.color

    # Perform surgery on sys.argv to remove the arguments which have already been processed by argparse
    sys.argv = sys.argv[:1] + unknown_args

    # Instantiate your cmd2 application
    app = ArgparsingApp(color)

    # And run your cmd2 application
    sys.exit(app.cmdloop())
