# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

from typing import List
import pytest

import cmd2
from cmd2 import utils

from .conftest import (
    complete_tester,
    normalize,
    run_cmd,
)


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
    cmd.poutput('Command with support functions: {}'.format(statement.args))


def help_command_with_support(cmd: cmd2.Cmd):
    cmd.poutput('Help for command_with_support')


def complete_command_with_support(cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
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


@cmd2.with_default_category('Command Set B')
class CommandSetB(cmd2.CommandSet):
    def __init__(self, arg1):
        super().__init__()
        self._arg1 = arg1

    def do_aardvark(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Aardvark!')

    def do_bat(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Banana Command"""
        cmd.poutput('Bat!!')

    def do_crocodile(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Crocodile!!')


@pytest.fixture
def command_sets_app():
    app = WithCommandSets()
    return app


@pytest.fixture()
def command_sets_manual():
    app = WithCommandSets(auto_load_commands=False)
    return app


def test_autoload_commands(command_sets_app):
    # verifies that, when autoload is enabled, CommandSets and registered functions all show up

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_app._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']


def test_custom_construct_commandsets():
    # Verifies that a custom initialized CommandSet loads correctly when passed into the constructor
    command_set = CommandSetB('foo')
    app = WithCommandSets(command_sets=[command_set])

    cmds_cats, cmds_doc, cmds_undoc, help_topics = app._build_command_info()
    assert 'Command Set B' in cmds_cats

    command_set_2 = CommandSetB('bar')
    with pytest.raises(ValueError):
        assert app.install_command_set(command_set_2)


def test_load_commands(command_sets_manual):
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    # start by verifying none of the installable commands are present
    assert 'AAA' not in cmds_cats
    assert 'Alone' not in cmds_cats
    assert 'Command Set' not in cmds_cats

    # install the `unbound` command
    command_sets_manual.install_registered_command('unbound')

    # verify that the same registered command can't be installed twice
    with pytest.raises(ValueError):
        assert command_sets_manual.install_registered_command('unbound')

    # verifies detection of unregistered commands
    with pytest.raises(KeyError):
        assert command_sets_manual.install_registered_command('nonexistent_command')

    # verifies that a duplicate function name is detected
    def do_unbound(cmd: cmd2.Cmd, statement: cmd2.Statement):
        """
        This function duplicates an existing command
        """
        cmd.poutput('Unbound Command: {}'.format(statement.args))

    with pytest.raises(KeyError):
        assert cmd2.register_command(do_unbound)

    # verify only the `unbound` command was installed
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']
    assert 'Alone' not in cmds_cats
    assert 'Command Set' not in cmds_cats

    # now install a command set and verify the commands are now present
    cmd_set = CommandSetA()
    command_sets_manual.install_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']

    # uninstall the `unbound` command and verify only it was uninstalled
    command_sets_manual.uninstall_command('unbound')

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' not in cmds_cats

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']

    # uninstall the command set and verify it is now also no longer accessible
    command_sets_manual.uninstall_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' not in cmds_cats
    assert 'Alone' not in cmds_cats
    assert 'Command Set' not in cmds_cats

    # reinstall the command set and verifyt is accessible but the `unbound` command isn't
    command_sets_manual.install_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'AAA' not in cmds_cats

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']


def test_command_functions(command_sets_manual):
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'AAA' not in cmds_cats

    out, err = run_cmd(command_sets_manual, 'command_with_support')
    assert 'is not a recognized command, alias, or macro' in err[0]

    out, err = run_cmd(command_sets_manual, 'help command_with_support')
    assert 'No help on command_with_support' in err[0]

    text = ''
    line = 'command_with_support'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    assert first_match is None

    # A bad command name gets rejected with an exception
    with pytest.raises(ValueError):
        assert command_sets_manual.install_command_function('>"',
                                                            do_command_with_support,
                                                            complete_command_with_support,
                                                            help_command_with_support)

    # create an alias to verify that it gets removed when the command is created
    out, err = run_cmd(command_sets_manual, 'alias create command_with_support run_pyscript')
    assert out == normalize("Alias 'command_with_support' created")

    command_sets_manual.install_registered_command('command_with_support')

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'AAA' in cmds_cats
    assert 'command_with_support' in cmds_cats['AAA']

    out, err = run_cmd(command_sets_manual, 'command_with_support')
    assert 'Command with support functions' in out[0]

    out, err = run_cmd(command_sets_manual, 'help command_with_support')
    assert 'Help for command_with_support' in out[0]

    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    assert first_match == 'Ham'

    text = ''
    line = 'command_with_support Ham'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match == 'Basket'

    command_sets_manual.uninstall_command('command_with_support')

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'AAA' not in cmds_cats

    out, err = run_cmd(command_sets_manual, 'command_with_support')
    assert 'is not a recognized command, alias, or macro' in err[0]

    out, err = run_cmd(command_sets_manual, 'help command_with_support')
    assert 'No help on command_with_support' in err[0]

    text = ''
    line = 'command_with_support'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    assert first_match is None

    # create an alias to verify that it gets removed when the command is created
    out, err = run_cmd(command_sets_manual, 'macro create command_with_support run_pyscript')
    assert out == normalize("Macro 'command_with_support' created")

    command_sets_manual.install_command_function('command_with_support',
                                                 do_command_with_support,
                                                 complete_command_with_support,
                                                 help_command_with_support)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'AAA' in cmds_cats
    assert 'command_with_support' in cmds_cats['AAA']

    out, err = run_cmd(command_sets_manual, 'command_with_support')
    assert 'Command with support functions' in out[0]

    out, err = run_cmd(command_sets_manual, 'help command_with_support')
    assert 'Help for command_with_support' in out[0]

    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    assert first_match == 'Ham'

    text = ''
    line = 'command_with_support Ham'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match == 'Basket'



def test_partial_with_passthru():

    def test_func(arg1, arg2):
        """Documentation Comment"""
        print('Do stuff {} - {}'.format(arg1, arg2))

    my_partial = cmd2.command_definition._partial_passthru(test_func, 1)

    setattr(test_func, 'Foo', 5)

    assert hasattr(my_partial, 'Foo')

    assert getattr(my_partial, 'Foo', None) == 5

    a = dir(test_func)
    b = dir(my_partial)
    assert a == b

    assert not hasattr(test_func, 'Bar')
    setattr(my_partial, 'Bar', 6)
    assert hasattr(test_func, 'Bar')

    assert getattr(test_func, 'Bar', None) == 6
