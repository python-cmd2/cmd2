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
    def __init__(self, color) -> None:
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
            size /= 1024
        elif args.unit == 'MB':
            size /= 1024 * 1024
        else:
            args.unit = 'bytes'
        size = round(size, 2)

        if args.comma:
            size = f'{size:,}'
        self.poutput(f'{size} {args.unit}')

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
    def do_print_args(self, args) -> None:
        """Print the arpgarse argument list this command was called with."""
        self.poutput(f'print_args was called with the following\n\targuments: {args!r}')

    unknownprint_parser = cmd2.Cmd2ArgumentParser()
    unknownprint_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    unknownprint_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    unknownprint_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')

    @cmd2.with_argparser(unknownprint_parser, with_unknown_args=True)
    @cmd2.with_category(ARGPARSE_PRINTING)
    def do_print_unknown(self, args, unknown) -> None:
        """Print the arpgarse argument list this command was called with, including unknown arguments."""
        self.poutput(f'print_unknown was called with the following arguments\n\tknown: {args!r}\n\tunknown: {unknown}')

    ## ------ Examples demonstrating how to use argparse subcommands -----

    sport_item_strs = ('Bat', 'Basket', 'Basketball', 'Football', 'Space Ball')

    # create the top-level parser for the base command
    base_parser = cmd2.Cmd2ArgumentParser()
    base_subparsers = base_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.add_argument('input_file', type=str, help='Input File')

    # create the parser for the "bar" subcommand
    parser_bar = base_subparsers.add_parser('bar', help='bar help')

    bar_subparsers = parser_bar.add_subparsers(title='layer3', help='help for 3rd layer of commands')
    parser_bar.add_argument('z', help='string')

    bar_subparsers.add_parser('apple', help='apple help')
    bar_subparsers.add_parser('artichoke', help='artichoke help')
    bar_subparsers.add_parser('cranberries', help='cranberries help')

    # create the parser for the "sport" subcommand
    parser_sport = base_subparsers.add_parser('sport', help='sport help')
    sport_arg = parser_sport.add_argument('sport', help='Enter name of a sport', choices=sport_item_strs)

    # create the top-level parser for the alternate command
    # The alternate command doesn't provide its own help flag
    base2_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    base2_subparsers = base2_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo2 = base2_subparsers.add_parser('foo', help='foo help')
    parser_foo2.add_argument('-x', type=int, default=1, help='integer')
    parser_foo2.add_argument('y', type=float, help='float')
    parser_foo2.add_argument('input_file', type=str, help='Input File')

    # create the parser for the "bar" subcommand
    parser_bar2 = base2_subparsers.add_parser('bar', help='bar help')

    bar2_subparsers = parser_bar2.add_subparsers(title='layer3', help='help for 3rd layer of commands')
    parser_bar2.add_argument('z', help='string')

    bar2_subparsers.add_parser('apple', help='apple help')
    bar2_subparsers.add_parser('artichoke', help='artichoke help')
    bar2_subparsers.add_parser('cranberries', help='cranberries help')

    # create the parser for the "sport" subcommand
    parser_sport2 = base2_subparsers.add_parser('sport', help='sport help')
    sport2_arg = parser_sport2.add_argument('sport', help='Enter name of a sport', choices=sport_item_strs)

    # subcommand functions for the base command
    def base_foo(self, args) -> None:
        """Foo subcommand of base command."""
        self.poutput(args.x * args.y)

    def base_bar(self, args) -> None:
        """Bar subcommand of base command."""
        self.poutput(f'(({args.z}))')

    def base_sport(self, args) -> None:
        """Sport subcommand of base command."""
        self.poutput(f'Sport is {args.sport}')

    # Set handler functions for the subcommands
    parser_foo.set_defaults(func=base_foo)
    parser_bar.set_defaults(func=base_bar)
    parser_sport.set_defaults(func=base_sport)

    @cmd2.with_argparser(base_parser)
    @cmd2.with_category(ARGPARSE_SUBCOMMANDS)
    def do_base(self, args) -> None:
        """Base command help."""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('base')

    @cmd2.with_argparser(base2_parser)
    @cmd2.with_category(ARGPARSE_SUBCOMMANDS)
    def do_alternate(self, args) -> None:
        """Alternate command help."""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('alternate')


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
