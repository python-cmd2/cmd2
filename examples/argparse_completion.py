#!/usr/bin/env python
# coding=utf-8
"""
A simple example demonstrating how to integrate tab completion with argparse-based commands.
"""
import argparse
from typing import Dict, List

from cmd2 import Cmd, Cmd2ArgumentParser, CompletionItem, with_argparser
from cmd2.utils import CompletionError, basic_complete

# Data source for argparse.choices
food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato']


def choices_function() -> List[str]:
    """Choices functions are useful when the choice list is dynamically generated (e.g. from data in a database)"""
    return ['a', 'dynamic', 'list', 'goes', 'here']


def completer_function(text: str, line: str, begidx: int, endidx: int) -> List[str]:
    """
    A tab completion function not dependent on instance data. Since custom tab completion operations commonly
    need to modify cmd2's instance variables related to tab completion, it will be rare to need a completer
    function. completer_method should be used in those cases.
    """
    match_against = ['a', 'dynamic', 'list', 'goes', 'here']
    return basic_complete(text, line, begidx, endidx, match_against)


def choices_completion_item() -> List[CompletionItem]:
    """Return CompletionItem instead of strings. These give more context to what's being tab completed."""
    items = \
        {
            1: "My item",
            2: "Another item",
            3: "Yet another item"
        }
    return [CompletionItem(item_id, description) for item_id, description in items.items()]


def choices_arg_tokens(arg_tokens: Dict[str, List[str]]) -> List[str]:
    """
    If a choices or completer function/method takes a value called arg_tokens, then it will be
    passed a dictionary that maps the command line tokens up through the one being completed
    to their argparse argument name.  All values of the arg_tokens dictionary are lists, even if
    a particular argument expects only 1 token.
    """
    # Check if choices_function flag has appeared
    values = ['choices_function', 'flag']
    if 'choices_function' in arg_tokens:
        values.append('is {}'.format(arg_tokens['choices_function'][0]))
    else:
        values.append('not supplied')
    return values


class ArgparseCompletion(Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

    def choices_method(self) -> List[str]:
        """Choices methods are useful when the choice list is based on instance data of your application"""
        return self.sport_item_strs

    def choices_completion_error(self) -> List[str]:
        """
        CompletionErrors can be raised if an error occurs while tab completing.

        Example use cases
            - Reading a database to retrieve a tab completion data set failed
            - A previous command line argument that determines the data set being completed is invalid
        """
        if self.debug:
            return self.sport_item_strs
        raise CompletionError("debug must be true")

    # Parser for example command
    example_parser = Cmd2ArgumentParser(description="Command demonstrating tab completion with argparse\n"
                                                    "Notice even the flags of this command tab complete")

    # Tab complete from a list using argparse choices. Set metavar if you don't
    # want the entire choices list showing in the usage text for this command.
    example_parser.add_argument('--choices', choices=food_item_strs, metavar="CHOICE",
                                help="tab complete using choices")

    # Tab complete from choices provided by a choices function and choices method
    example_parser.add_argument('--choices_function', choices_function=choices_function,
                                help="tab complete using a choices_function")
    example_parser.add_argument('--choices_method', choices_method=choices_method,
                                help="tab complete using a choices_method")

    # Tab complete using a completer function and completer method
    example_parser.add_argument('--completer_function', completer_function=completer_function,
                                help="tab complete using a completer_function")
    example_parser.add_argument('--completer_method', completer_method=Cmd.path_complete,
                                help="tab complete using a completer_method")

    # Demonstrate raising a CompletionError while tab completing
    example_parser.add_argument('--completion_error', choices_method=choices_completion_error,
                                help="raise a CompletionError while tab completing if debug is False")

    # Demonstrate returning CompletionItems instead of strings
    example_parser.add_argument('--completion_item', choices_function=choices_completion_item, metavar="ITEM_ID",
                                descriptive_header="Description",
                                help="demonstrate use of CompletionItems")

    # Demonstrate use of arg_tokens dictionary
    example_parser.add_argument('--arg_tokens', choices_function=choices_arg_tokens,
                                help="demonstrate use of arg_tokens dictionary")

    @with_argparser(example_parser)
    def do_example(self, _: argparse.Namespace) -> None:
        """The example command"""
        self.poutput("I do nothing")


if __name__ == '__main__':
    import sys
    app = ArgparseCompletion()
    sys.exit(app.cmdloop())
