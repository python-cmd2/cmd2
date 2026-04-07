"""Tests help categories for Cmd and CommandSet objects."""

import argparse

import cmd2
from cmd2 import (
    Cmd2ArgumentParser,
    CommandSet,
    with_argparser,
    with_category,
)


class NoCategoryCmd(cmd2.Cmd):
    """Example to demonstrate a Cmd-based class which does not define its own DEFAULT_CATEGORY.

    Its commands will inherit the parent class's DEFAULT_CATEGORY.
    """

    def do_inherit(self, _: cmd2.Statement) -> None:
        """This function has a docstring.

        Since this class does NOT define its own DEFAULT_CATEGORY,
        this command will show in cmd2.Cmd.DEFAULT_CATEGORY
        """


class CategoryCmd(cmd2.Cmd):
    """Example to demonstrate custom DEFAULT_CATEGORY in a Cmd-based class.

    It also includes functions to fully exercise Cmd._build_command_info.
    """

    DEFAULT_CATEGORY = "CategoryCmd Commands"

    def do_cmd_command(self, _: cmd2.Statement) -> None:
        """The cmd command.

        Since this class DOES define its own DEFAULT_CATEGORY,
        this command will show in CategoryCmd.DEFAULT_CATEGORY
        """

    @with_argparser(Cmd2ArgumentParser(description="Overridden quit command"))
    def do_quit(self, _: argparse.Namespace) -> None:
        """This function overrides the cmd2.Cmd quit command.

        Since this override does not use the with_category decorator,
        it will be in CategoryCmd.DEFAULT_CATEGORY and not cmd2.Cmd.DEFAULT_CATEGORY.
        """

    @with_category(cmd2.Cmd.DEFAULT_CATEGORY)
    @with_argparser(Cmd2ArgumentParser(description="Overridden shortcuts command"))
    def do_shortcuts(self, _: argparse.Namespace) -> None:
        """This function overrides the cmd2.Cmd shortcut command.

        It also uses the with_category decorator to keep shortcuts in
        cmd2.Cmd.DEFAULT_CATEGORY for the parent class.
        """

    def do_has_help_func(self, _: cmd2.Statement) -> None:
        """This command has a help function."""

    def help_has_help_func(self) -> None:
        """Help function for the has_help_func command."""
        self.poutput("has_help_func help text.")

    def help_coding(self) -> None:
        """This help function not tied to a command.

        It will be in help topics.
        """
        self.poutput("Read a book.")


def test_no_category_cmd() -> None:
    app = NoCategoryCmd()
    cmds_cats, _help_topics = app._build_command_info()
    assert "inherit" in cmds_cats[cmd2.Cmd.DEFAULT_CATEGORY]


def test_category_cmd() -> None:
    app = CategoryCmd()
    cmds_cats, help_topics = app._build_command_info()

    assert "cmd_command" in cmds_cats[CategoryCmd.DEFAULT_CATEGORY]
    assert "quit" in cmds_cats[CategoryCmd.DEFAULT_CATEGORY]
    assert "shortcuts" in cmds_cats[cmd2.Cmd.DEFAULT_CATEGORY]
    assert "has_help_func" in cmds_cats[CategoryCmd.DEFAULT_CATEGORY]
    assert "coding" in help_topics


class NoCategoryCommandSet(CommandSet):
    """Example to demonstrate a CommandSet which does not define its own DEFAULT_CATEGORY.

    Its commands will inherit the parent class's DEFAULT_CATEGORY.
    """

    def do_inherit(self, _: cmd2.Statement) -> None:
        """This function has a docstring.

        Since this class does NOT define its own DEFAULT_CATEGORY,
        this command will show in CommandSet.DEFAULT_CATEGORY
        """


class CategoryCommandSet(CommandSet):
    """Example to demonstrate custom DEFAULT_CATEGORY in a CommandSet."""

    DEFAULT_CATEGORY = "CategoryCommandSet Commands"

    def do_cmdset_command(self, _: cmd2.Statement) -> None:
        """The cmdset command.

        Since this class DOES define its own DEFAULT_CATEGORY,
        this command will show in CategoryCommandSet.DEFAULT_CATEGORY
        """


def test_no_category_command_set() -> None:
    app = cmd2.Cmd()
    app.register_command_set(NoCategoryCommandSet())
    cmds_cats, _help_topics = app._build_command_info()
    assert "inherit" in cmds_cats[CommandSet.DEFAULT_CATEGORY]


def test_category_command_set() -> None:
    app = cmd2.Cmd()
    app.register_command_set(CategoryCommandSet())
    cmds_cats, _help_topics = app._build_command_info()
    assert "cmdset_command" in cmds_cats[CategoryCommandSet.DEFAULT_CATEGORY]
