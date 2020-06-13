# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

from typing import List
import pytest

import cmd2
from cmd2 import utils


# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock


@cmd2.register_command
@cmd2.with_category("AAA")
def do_unbound(cmd: cmd2.Cmd, statement: cmd2.Statement):
    """
    This is an example of registering an unbound function

    :param cmd:
    :param statement:
    :return:
    """
    cmd.poutput('Unbound Command: {}'.format(statement.args))


@cmd2.register_command
@cmd2.with_category("AAA")
def do_command_with_support(cmd: cmd2.Cmd, statement: cmd2.Statement):
    """
    This is an example of registering an unbound function

    :param cmd:
    :param statement:
    :return:
    """
    cmd.poutput('Unbound Command: {}'.format(statement.args))


def help_command_with_support(cmd: cmd2.Cmd):
    cmd.poutput('Help for command_with_support')


def complete_command_with_support(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
    """Completion function for do_index_based"""
    food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato']
    sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']

    index_dict = \
        {
            1: food_item_strs,  # Tab complete food items at index 1 in command line
            2: sport_item_strs,  # Tab complete sport items at index 2 in command line
            3: cmd.path_complete,  # Tab complete using path_complete function at index 3 in command line
        }

    return cmd.index_based_complete(text, line, begidx, endidx, index_dict=index_dict)


@cmd2.with_default_category('Command Set')
class CommandSetA(cmd2.CommandSet):
    def do_apple(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Apple!')

    def do_banana(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Banana Command"""
        cmd.poutput('Banana!!')

    def do_cranberry(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Cranberry!!')

    def help_cranberry(self, cmd: cmd2.Cmd):
        cmd.stdout.write('This command does diddly squat...\n')

    def do_durian(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Durian Command"""
        cmd.poutput('Durian!!')

    def complete_durian(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return utils.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    @cmd2.with_category('Alone')
    def do_elderberry(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Elderberry!!')


class WithCommandSets(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@pytest.fixture
def command_sets_app():
    app = WithCommandSets()
    return app

@pytest.fixture()
def command_sets_manual():
    app = WithCommandSets(auto_load_commands=False)
    return app


def test_autoload_commands(command_sets_app):
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_app._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']


def test_load_commands(command_sets_manual):
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' not in cmds_cats

    assert 'Alone' not in cmds_cats

    assert 'Command Set' not in cmds_cats

    command_sets_manual.install_command_function('unbound', do_unbound, None, None)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']

    assert 'Alone' not in cmds_cats

    assert 'Command Set' not in cmds_cats

    cmd_set = CommandSetA()

    command_sets_manual.install_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']

    command_sets_manual.uninstall_command('unbound')

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' not in cmds_cats

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']

    command_sets_manual.uninstall_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' not in cmds_cats

    assert 'Alone' not in cmds_cats

    assert 'Command Set' not in cmds_cats
