#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating how to use flag and index based tab-completion functions
"""
import argparse
import functools

import cmd2
from cmd2 import with_argparser, with_argument_list, flag_based_complete, index_based_complete, path_complete

# List of strings used with flag and index based completion functions
food_item_strs = ['Pizza', 'Hamburger', 'Ham', 'Potato']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football']

# Dictionary used with flag based completion functions
flag_dict = \
    {
        '-f': food_item_strs,        # Tab-complete food items after -f flag in command line
        '--food': food_item_strs,    # Tab-complete food items after --food flag in command line
        '-s': sport_item_strs,       # Tab-complete sport items after -s flag in command line
        '--sport': sport_item_strs,  # Tab-complete sport items after --sport flag in command line
        '-o': path_complete,         # Tab-complete using path_complete function after -o flag in command line
        '--other': path_complete,    # Tab-complete using path_complete function after --other flag in command line
    }

# Dictionary used with index based completion functions
index_dict = \
    {
        1: food_item_strs,   # Tab-complete food items at index 1 in command line
        2: sport_item_strs,  # Tab-complete sport items at index 2 in command line
        3: path_complete,    # Tab-complete using path_complete function at index 3 in command line
    }


class TabCompleteExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""

    def __init__(self):
        cmd2.Cmd.__init__(self)

    add_item_parser = argparse.ArgumentParser()
    add_item_group = add_item_parser.add_mutually_exclusive_group()
    add_item_group.add_argument('-f', '--food', help='Adds food item')
    add_item_group.add_argument('-s', '--sport', help='Adds sport item')
    add_item_group.add_argument('-o', '--other', help='Adds other item')

    @with_argparser(add_item_parser)
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
    complete_add_item = functools.partial(flag_based_complete, flag_dict=flag_dict)

    @with_argument_list
    def do_list_item(self, args):
        """List item command help"""
        self.poutput("You listed {}".format(args))

    # Add index-based tab-completion to list_item command
    complete_list_item = functools.partial(index_based_complete, index_dict=index_dict)


if __name__ == '__main__':
    app = TabCompleteExample()
    app.cmdloop()
