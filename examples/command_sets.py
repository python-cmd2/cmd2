#!/usr/bin/env python3
"""Example revolving around the CommandSet feature for modularizing commands.

It attempts to cover basic usage as well as more complex usage including dynamic loading and unloading of CommandSets, using
CommandSets to add subcommands, as well as how to categorize command in CommandSets. Here we have kept the implementation for
most commands trivial because the intent is to focus on the CommandSet feature set.

The `AutoLoadCommandSet` is a basic command set which is loaded automatically at application startup and stays loaded until
application exit. Ths is the simplest case of simply modularizing command definitions to different classes and/or files.

The `LoadableFruits` and `LoadableVegetables` CommandSets are dynamically loadable and un-loadable at runtime using the `load`
and `unload` commands. This demonstrates the ability to load and unload CommandSets based on application state. Each of these
also loads a subcommand of the `cut` command.
"""

import argparse

import cmd2
from cmd2 import (
    CommandSet,
    with_argparser,
    with_category,
    with_default_category,
)

COMMANDSET_BASIC = "Basic CommandSet"
COMMANDSET_DYNAMIC = "Dynamic CommandSet"
COMMANDSET_LOAD_UNLOAD = "Loading and Unloading CommandSets"
COMMANDSET_SUBCOMMAND = "Subcommands with CommandSet"


@with_default_category(COMMANDSET_BASIC)
class AutoLoadCommandSet(CommandSet):
    def __init__(self) -> None:
        """CommandSet class for auto-loading commands at startup."""
        super().__init__()

    def do_hello(self, _: cmd2.Statement) -> None:
        """Print hello."""
        self._cmd.poutput('Hello')

    def do_world(self, _: cmd2.Statement) -> None:
        """Print World."""
        self._cmd.poutput('World')


@with_default_category(COMMANDSET_DYNAMIC)
class LoadableFruits(CommandSet):
    def __init__(self) -> None:
        """CommandSet class for dynamically loading commands related to fruits."""
        super().__init__()

    def do_apple(self, _: cmd2.Statement) -> None:
        """Print Apple."""
        self._cmd.poutput('Apple')

    def do_banana(self, _: cmd2.Statement) -> None:
        """Print Banana."""
        self._cmd.poutput('Banana')

    banana_description = "Cut a banana"
    banana_parser = cmd2.Cmd2ArgumentParser(description=banana_description)
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help=banana_description.lower())
    def cut_banana(self, ns: argparse.Namespace) -> None:
        """Cut banana."""
        self._cmd.poutput('cutting banana: ' + ns.direction)


@with_default_category(COMMANDSET_DYNAMIC)
class LoadableVegetables(CommandSet):
    def __init__(self) -> None:
        """CommandSet class for dynamically loading commands related to vegetables."""
        super().__init__()

    def do_arugula(self, _: cmd2.Statement) -> None:
        "Print Arguula."
        self._cmd.poutput('Arugula')

    def do_bokchoy(self, _: cmd2.Statement) -> None:
        """Print Bok Choy."""
        self._cmd.poutput('Bok Choy')

    bokchoy_description = "Cut some bokchoy"
    bokchoy_parser = cmd2.Cmd2ArgumentParser(description=bokchoy_description)
    bokchoy_parser.add_argument('style', choices=['quartered', 'diced'])

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser, help=bokchoy_description.lower())
    def cut_bokchoy(self, ns: argparse.Namespace) -> None:
        """Cut bokchoy."""
        self._cmd.poutput('Bok Choy: ' + ns.style)


class CommandSetApp(cmd2.Cmd):
    """CommandSets are automatically loaded. Nothing needs to be done."""

    def __init__(self) -> None:
        """Cmd2 application for demonstrating the CommandSet features."""
        # This prevents all CommandSets from auto-loading, which is necessary if you don't want some to load at startup
        super().__init__(auto_load_commands=False)

        self.register_command_set(AutoLoadCommandSet())

        # Store the dyanmic CommandSet classes for ease of loading and unloading
        self._fruits = LoadableFruits()
        self._vegetables = LoadableVegetables()

        self.intro = 'The CommandSet feature allows defining commands in multiple files and the dynamic load/unload at runtime'

    load_parser = cmd2.Cmd2ArgumentParser()
    load_parser.add_argument('cmds', choices=['fruits', 'vegetables'])

    @with_argparser(load_parser)
    @with_category(COMMANDSET_LOAD_UNLOAD)
    def do_load(self, ns: argparse.Namespace) -> None:
        """Load a CommandSet at runtime."""
        if ns.cmds == 'fruits':
            try:
                self.register_command_set(self._fruits)
                self.poutput('Fruits loaded')
            except ValueError:
                self.poutput('Fruits already loaded')

        if ns.cmds == 'vegetables':
            try:
                self.register_command_set(self._vegetables)
                self.poutput('Vegetables loaded')
            except ValueError:
                self.poutput('Vegetables already loaded')

    @with_argparser(load_parser)
    @with_category(COMMANDSET_LOAD_UNLOAD)
    def do_unload(self, ns: argparse.Namespace) -> None:
        """Unload a CommandSet at runtime."""
        if ns.cmds == 'fruits':
            self.unregister_command_set(self._fruits)
            self.poutput('Fruits unloaded')

        if ns.cmds == 'vegetables':
            self.unregister_command_set(self._vegetables)
            self.poutput('Vegetables unloaded')

    cut_parser = cmd2.Cmd2ArgumentParser()
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    @with_argparser(cut_parser)
    @with_category(COMMANDSET_SUBCOMMAND)
    def do_cut(self, ns: argparse.Namespace) -> None:
        """Intended to be used with dyanmically loaded subcommands specifically."""
        handler = ns.cmd2_handler.get()
        if handler is not None:
            handler(ns)
        else:
            # No subcommand was provided, so call help
            self.poutput('This command does nothing without sub-parsers registered')
            self.do_help('cut')


if __name__ == '__main__':
    app = CommandSetApp()
    app.cmdloop()
