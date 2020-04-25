#!/usr/bin/env python3
# coding=utf-8
"""A simple example demonstrating how to use Argparse to support subcommands.


This example shows an easy way for a single command to have many subcommands, each of which takes different arguments
and provides separate contextual help.
"""
import argparse

import cmd2

sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

# create the top-level parser for the base command
base_parser = argparse.ArgumentParser()
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
base2_parser = argparse.ArgumentParser(add_help=False)
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


class SubcommandsExample(cmd2.Cmd):
    """
    Example cmd2 application where we a base command which has a couple subcommands
    and the "sport" subcommand has tab completion enabled.
    """
    def __init__(self):
        super().__init__()

    # subcommand functions for the base command
    def base_foo(self, args):
        """foo subcommand of base command"""
        self.poutput(args.x * args.y)

    def base_bar(self, args):
        """bar subcommand of base command"""
        self.poutput('((%s))' % args.z)

    def base_sport(self, args):
        """sport subcommand of base command"""
        self.poutput('Sport is {}'.format(args.sport))

    # Set handler functions for the subcommands
    parser_foo.set_defaults(func=base_foo)
    parser_bar.set_defaults(func=base_bar)
    parser_sport.set_defaults(func=base_sport)

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

    @cmd2.with_argparser(base2_parser)
    def do_alternate(self, args):
        """Alternate command help"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('alternate')


if __name__ == '__main__':
    import sys
    app = SubcommandsExample()
    sys.exit(app.cmdloop())
