#!/usr/bin/env python
# coding=utf-8
"""
A complex example demonstrating a variety of methods to load CommandSets using a mix of command decorators
with examples of how to integrate tab completion with argparse-based commands.
"""
import argparse
from typing import (
    Iterable,
    List,
    Optional,
)

from modular_commands.commandset_basic import (  # noqa: F401
    BasicCompletionCommandSet,
)
from modular_commands.commandset_complex import (  # noqa: F401
    CommandSetA,
)
from modular_commands.commandset_custominit import (  # noqa: F401
    CustomInitCommandSet,
)

from cmd2 import (
    Cmd,
    Cmd2ArgumentParser,
    CommandSet,
    with_argparser,
)


class WithCommandSets(Cmd):
    def __init__(self, command_sets: Optional[Iterable[CommandSet]] = None):
        super().__init__(command_sets=command_sets)
        self.sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

    def choices_provider(self) -> List[str]:
        """A choices provider is useful when the choice list is based on instance data of your application"""
        return self.sport_item_strs

    # Parser for example command
    example_parser = Cmd2ArgumentParser(
        description="Command demonstrating tab completion with argparse\n" "Notice even the flags of this command tab complete"
    )

    # Tab complete from a list using argparse choices. Set metavar if you don't
    # want the entire choices list showing in the usage text for this command.
    example_parser.add_argument(
        '--choices', choices=['some', 'choices', 'here'], metavar="CHOICE", help="tab complete using choices"
    )

    # Tab complete from choices provided by a choices provider
    example_parser.add_argument(
        '--choices_provider', choices_provider=choices_provider, help="tab complete using a choices_provider"
    )

    # Tab complete using a completer
    example_parser.add_argument('--completer', completer=Cmd.path_complete, help="tab complete using a completer")

    @with_argparser(example_parser)
    def do_example(self, _: argparse.Namespace) -> None:
        """The example command"""
        self.poutput("I do nothing")


if __name__ == '__main__':
    import sys

    print("Starting")
    my_sets = [CustomInitCommandSet('First argument', 'Second argument')]
    app = WithCommandSets(command_sets=my_sets)
    sys.exit(app.cmdloop())
