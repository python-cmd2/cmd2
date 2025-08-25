#!/usr/bin/env python
"""A simple example demonstrating how to integrate tab completion with argparse-based commands."""

import argparse

import rich.box
from rich.style import Style
from rich.table import Table
from rich.text import Text

from cmd2 import (
    Cmd,
    Cmd2ArgumentParser,
    Cmd2Style,
    Color,
    CompletionError,
    CompletionItem,
    with_argparser,
)

# Data source for argparse.choices
food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato']


class ArgparseCompletion(Cmd):
    def __init__(self) -> None:
        super().__init__(include_ipy=True)
        self.sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

    def choices_provider(self) -> list[str]:
        """A choices provider is useful when the choice list is based on instance data of your application."""
        return self.sport_item_strs

    def choices_completion_error(self) -> list[str]:
        """CompletionErrors can be raised if an error occurs while tab completing.

        Example use cases
            - Reading a database to retrieve a tab completion data set failed
            - A previous command line argument that determines the data set being completed is invalid
        """
        if self.debug:
            return self.sport_item_strs
        raise CompletionError("debug must be true")

    def choices_completion_item(self) -> list[CompletionItem]:
        """Return CompletionItem instead of strings. These give more context to what's being tab completed."""
        fancy_item = Text.assemble(
            "These things can\ncontain newlines and\n",
            Text("styled text!!", style=Style(color=Color.BRIGHT_YELLOW, underline=True)),
        )

        table_item = Table(
            "Left Column",
            "Right Column",
            box=rich.box.ROUNDED,
            border_style=Cmd2Style.TABLE_BORDER,
        )
        table_item.add_row("Yes, it's true.", "CompletionItems can")
        table_item.add_row("even display description", "data in tables!")

        items = {
            1: "My item",
            2: "Another item",
            3: "Yet another item",
            4: fancy_item,
            5: table_item,
        }
        return [CompletionItem(item_id, [description]) for item_id, description in items.items()]

    def choices_arg_tokens(self, arg_tokens: dict[str, list[str]]) -> list[str]:
        """If a choices or completer function/method takes a value called arg_tokens, then it will be
        passed a dictionary that maps the command line tokens up through the one being completed
        to their argparse argument name.  All values of the arg_tokens dictionary are lists, even if
        a particular argument expects only 1 token.
        """
        # Check if choices_provider flag has appeared
        values = ['choices_provider', 'flag']
        if 'choices_provider' in arg_tokens:
            values.append('is {}'.format(arg_tokens['choices_provider'][0]))
        else:
            values.append('not supplied')
        return values

    # Parser for example command
    example_parser = Cmd2ArgumentParser(
        description="Command demonstrating tab completion with argparse\nNotice even the flags of this command tab complete"
    )

    # Tab complete from a list using argparse choices. Set metavar if you don't
    # want the entire choices list showing in the usage text for this command.
    example_parser.add_argument('--choices', choices=food_item_strs, metavar="CHOICE", help="tab complete using choices")

    # Tab complete from choices provided by a choices_provider
    example_parser.add_argument(
        '--choices_provider', choices_provider=choices_provider, help="tab complete using a choices_provider"
    )

    # Tab complete using a completer
    example_parser.add_argument('--completer', completer=Cmd.path_complete, help="tab complete using a completer")

    # Demonstrate raising a CompletionError while tab completing
    example_parser.add_argument(
        '--completion_error',
        choices_provider=choices_completion_error,
        help="raise a CompletionError while tab completing if debug is False",
    )

    # Demonstrate returning CompletionItems instead of strings
    example_parser.add_argument(
        '--completion_item',
        choices_provider=choices_completion_item,
        metavar="ITEM_ID",
        descriptive_headers=["Description"],
        help="demonstrate use of CompletionItems",
    )

    # Demonstrate use of arg_tokens dictionary
    example_parser.add_argument(
        '--arg_tokens', choices_provider=choices_arg_tokens, help="demonstrate use of arg_tokens dictionary"
    )

    @with_argparser(example_parser)
    def do_example(self, _: argparse.Namespace) -> None:
        """The example command."""
        self.poutput("I do nothing")


if __name__ == '__main__':
    import sys

    app = ArgparseCompletion()
    sys.exit(app.cmdloop())
