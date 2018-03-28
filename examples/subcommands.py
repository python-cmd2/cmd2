#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating how to use Argparse to support subcommands.


This example shows an easy way for a single command to have many subcommands, each of which takes different arguments
and provides separate contextual help.
"""
import argparse

import cmd2
from cmd2 import with_argparser

sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

class SubcommandsExample(cmd2.Cmd):
    """
    Example cmd2 application where we a base command which has a couple subcommands
    and the "sport" subcommand has tab completion enabled.
    """

    def __init__(self):
        cmd2.Cmd.__init__(self)

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

    # noinspection PyUnusedLocal
    def complete_base_sport(self, text, line, begidx, endidx):
        """ Adds tab completion to base sport subcommand """
        index_dict = {1: sport_item_strs}
        return self.index_based_complete(text, line, begidx, endidx, index_dict)

    # create the top-level parser for the base command
    base_parser = argparse.ArgumentParser(prog='base')
    base_subparsers = base_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.set_defaults(func=base_foo)

    # create the parser for the "bar" subcommand
    parser_bar = base_subparsers.add_parser('bar', help='bar help')
    parser_bar.add_argument('z', help='string')
    parser_bar.set_defaults(func=base_bar)

    # create the parser for the "sport" subcommand
    parser_sport = base_subparsers.add_parser('sport', help='sport help')
    parser_sport.add_argument('sport', help='Enter name of a sport')

    # Set both a function and tab completer for the "sport" subcommand
    parser_sport.set_defaults(func=base_sport, completer=complete_base_sport)

    @with_argparser(base_parser)
    def do_base(self, args):
        """Base command help"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('base')

    # Enable tab completion of base to make sure the subcommands' completers get called.
    complete_base = cmd2.Cmd.cmd_with_subs_completer


if __name__ == '__main__':
    app = SubcommandsExample()
    app.cmdloop()
