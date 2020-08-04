#!/usr/bin/env python3
# coding=utf-8
"""A simple example demonstracting modular subcommand loading through CommandSets

In this example, there are loadable CommandSets defined. Each CommandSet has 1 subcommand defined that will be
attached to the 'cut' command.

The cut command is implemented with the `do_cut` function that has been tagged as an argparse command.

The `load` and `unload` command will load and unload the CommandSets. The available top level commands as well as
subcommands to the `cut` command will change depending on which CommandSets are loaded.
"""
import argparse
import cmd2
from cmd2 import CommandSet, with_argparser, with_category, with_default_category


@with_default_category('Fruits')
class LoadableFruits(CommandSet):
    def __init__(self):
        super().__init__()

    def do_apple(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Apple')

    banana_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser)
    def cut_banana(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        """Cut banana"""
        cmd.poutput('cutting banana: ' + ns.direction)


@with_default_category('Vegetables')
class LoadableVegetables(CommandSet):
    def __init__(self):
        super().__init__()

    def do_arugula(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Arugula')

    bokchoy_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    bokchoy_parser.add_argument('style', choices=['quartered', 'diced'])

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Bok Choy')


class ExampleApp(cmd2.Cmd):
    """
    CommandSets are automatically loaded. Nothing needs to be done.
    """

    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, auto_load_commands=False, **kwargs)

        self._fruits = LoadableFruits()
        self._vegetables = LoadableVegetables()

    load_parser = cmd2.Cmd2ArgumentParser('load')
    load_parser.add_argument('cmds', choices=['fruits', 'vegetables'])

    @with_argparser(load_parser)
    @with_category('Command Loading')
    def do_load(self, ns: argparse.Namespace):
        if ns.cmds == 'fruits':
            try:
                self.install_command_set(self._fruits)
                self.poutput('Fruits loaded')
            except ValueError:
                self.poutput('Fruits already loaded')

        if ns.cmds == 'vegetables':
            try:
                self.install_command_set(self._vegetables)
                self.poutput('Vegetables loaded')
            except ValueError:
                self.poutput('Vegetables already loaded')

    @with_argparser(load_parser)
    def do_unload(self, ns: argparse.Namespace):
        if ns.cmds == 'fruits':
            self.uninstall_command_set(self._fruits)
            self.poutput('Fruits unloaded')

        if ns.cmds == 'vegetables':
            self.uninstall_command_set(self._vegetables)
            self.poutput('Vegetables unloaded')

    cut_parser = cmd2.Cmd2ArgumentParser('cut')
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    @with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace):
        handler = ns.get_handler()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            self.poutput('This command does nothing without sub-parsers registered')
            self.do_help('cut')


if __name__ == '__main__':
    app = ExampleApp()
    app.cmdloop()
