#!/usr/bin/env python
# coding=utf-8
"""
A simple example demonstrating how to enable tab completion by assigning a completer function to do_* commands.
This also demonstrates capabilities of the following completer methods included with cmd2:
- flag_based_complete
- index_based_complete
- delimiter_completer

For an example enabling tab completion with argparse, see argparse_completion.py
"""
import argparse
import functools

import cmd2

# List of strings used with completion functions
food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

file_strs = \
    [
        '/home/user/file.db',
        '/home/user/file space.db',
        '/home/user/another.db',
        '/home/other user/maps.db',
        '/home/other user/tests.db'
    ]


class TabCompleteExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""
    def __init__(self):
        super().__init__()

    # The add_item command uses flag_based_complete
    add_item_parser = argparse.ArgumentParser()
    add_item_group = add_item_parser.add_mutually_exclusive_group()
    add_item_group.add_argument('-f', '--food', help='Adds food item')
    add_item_group.add_argument('-s', '--sport', help='Adds sport item')
    add_item_group.add_argument('-o', '--other', help='Adds other item')

    @cmd2.with_argparser(add_item_parser)
    def do_add_item(self, args):
        """Add item command help"""
        if args.food:
            add_item = args.food
        elif args.sport:
            add_item = args.sport
        elif args.other:
            add_item = args.other
        else:
            add_item = 'no items'

        self.poutput("You added {}".format(add_item))

    # Add flag-based tab-completion to add_item command
    def complete_add_item(self, text, line, begidx, endidx):
        flag_dict = \
            {
                # Tab-complete food items after -f and --food flags in command line
                '-f': food_item_strs,
                '--food': food_item_strs,

                # Tab-complete sport items after -s and --sport flags in command line
                '-s': sport_item_strs,
                '--sport': sport_item_strs,

                # Tab-complete using path_complete function after -o and --other flags in command line
                '-o': self.path_complete,
                '--other': self.path_complete,
            }

        return self.flag_based_complete(text, line, begidx, endidx, flag_dict=flag_dict)

    # The list_item command uses index_based_complete
    @cmd2.with_argument_list
    def do_list_item(self, args):
        """List item command help"""
        self.poutput("You listed {}".format(args))

    # Add index-based tab-completion to list_item command
    def complete_list_item(self, text, line, begidx, endidx):
        index_dict = \
            {
                1: food_item_strs,  # Tab-complete food items at index 1 in command line
                2: sport_item_strs,  # Tab-complete sport items at index 2 in command line
                3: self.path_complete,  # Tab-complete using path_complete function at index 3 in command line
            }

        return self.index_based_complete(text, line, begidx, endidx, index_dict=index_dict)

    # The file_list command uses delimiter_complete
    def do_file_list(self, statement: cmd2.Statement):
        """List files entered on command line"""
        self.poutput("You selected: {}".format(statement.args))

    # Use a partialmethod to set arguments to delimiter_complete
    complete_file_list = functools.partialmethod(cmd2.Cmd.delimiter_complete, match_against=file_strs, delimiter='/')


if __name__ == '__main__':
    import sys
    app = TabCompleteExample()
    sys.exit(app.cmdloop())
