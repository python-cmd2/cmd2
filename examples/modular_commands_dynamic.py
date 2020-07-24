#!/usr/bin/env python3
# coding=utf-8
"""
Simple example demonstrating dynamic CommandSet loading and unloading.

There are 2 CommandSets defined. ExampleApp sets the `auto_load_commands` flag to false.

The `load` and `unload` commands will load and unload the CommandSets. The available commands will change depending
on which CommandSets are loaded
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

    def do_banana(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Banana')


@with_default_category('Vegetables')
class LoadableVegetables(CommandSet):
    def __init__(self):
        super().__init__()

    def do_arugula(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Arugula')

    def do_bokchoy(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Bok Choy')


class ExampleApp(cmd2.Cmd):
    """
    CommandSets are loaded via the `load` and `unload` commands
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


if __name__ == '__main__':
    app = ExampleApp()
    app.cmdloop()
