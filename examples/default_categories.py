#!/usr/bin/env python3
"""Example demonstrating the DEFAULT_CATEGORY class variable for Cmd and CommandSet.

In cmd2 4.0, command categorization is driven by the DEFAULT_CATEGORY class variable.
This example shows:
1. How a Cmd class defines its own default category.
2. How a CommandSet defines its own default category.
3. How overriding a framework command moves it to the child class's category.
4. How to use @with_category to manually override the automatic categorization.
"""

import argparse

import cmd2
from cmd2 import (
    Cmd2ArgumentParser,
    CommandSet,
    with_argparser,
    with_category,
)


class MyPlugin(CommandSet):
    """A CommandSet that defines its own category."""

    DEFAULT_CATEGORY = "Plugin Commands"

    def do_plugin_action(self, _: cmd2.Statement) -> None:
        """A command defined in a CommandSet."""
        self._cmd.poutput("Plugin action executed")


class CategoryApp(cmd2.Cmd):
    """An application demonstrating various categorization scenarios."""

    # This sets the default category for all commands defined in this class
    DEFAULT_CATEGORY = "Application Commands"

    # This overrides the category for the cmd2 built-in commands
    cmd2.Cmd.DEFAULT_CATEGORY = "Cmd2 Shell Commands"

    def __init__(self) -> None:
        super().__init__()
        # Register a command set to show how its categories integrate
        self.register_command_set(MyPlugin())

    def do_app_command(self, _: cmd2.Statement) -> None:
        """A standard command defined in the child class."""
        self.poutput("Application command executed")

    @with_argparser(Cmd2ArgumentParser(description="Overridden quit command"))
    def do_quit(self, _: argparse.Namespace) -> bool | None:
        """Overriding a built-in command without a decorator moves it to our category."""
        return super().do_quit("")

    @with_category(cmd2.Cmd.DEFAULT_CATEGORY)
    @with_argparser(Cmd2ArgumentParser(description="Overridden shortcuts command"))
    def do_shortcuts(self, _: argparse.Namespace) -> None:
        """Overriding with @with_category(cmd2.Cmd.DEFAULT_CATEGORY) keeps it cmd2's category."""
        super().do_shortcuts("")


if __name__ == '__main__':
    import sys

    app = CategoryApp()
    app.poutput("Type 'help' to see how the commands are categorized.\n")
    sys.exit(app.cmdloop())
