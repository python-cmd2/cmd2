# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

import argparse
from typing import List

import pytest

import cmd2
from cmd2 import utils
from cmd2_ext_test import ExternalTestMixin


@cmd2.with_default_category('Fruits')
class CommandSetA(cmd2.CommandSet):
    def do_apple(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Apple!')

    def do_banana(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Banana Command"""
        cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser('cranberry')
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser_and_unknown_args(cranberry_parser)
    def do_cranberry(self, cmd: cmd2.Cmd, ns: argparse.Namespace, unknown: List[str]):
        cmd.poutput('Cranberry {}!!'.format(ns.arg1))
        if unknown and len(unknown):
            cmd.poutput('Unknown: ' + ', '.join(['{}']*len(unknown)).format(*unknown))
        cmd.last_result = {'arg1': ns.arg1,
                           'unknown': unknown}

    def help_cranberry(self, cmd: cmd2.Cmd):
        cmd.stdout.write('This command does diddly squat...\n')

    @cmd2.with_argument_list
    @cmd2.with_category('Also Alone')
    def do_durian(self, cmd: cmd2.Cmd, args: List[str]):
        """Durian Command"""
        cmd.poutput('{} Arguments: '.format(len(args)))
        cmd.poutput(', '.join(['{}']*len(args)).format(*args))
        cmd.last_result = {'args': args}

    def complete_durian(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return utils.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    elderberry_parser = cmd2.Cmd2ArgumentParser('elderberry')
    elderberry_parser.add_argument('arg1')

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(elderberry_parser)
    def do_elderberry(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        cmd.poutput('Elderberry {}!!'.format(ns.arg1))
        cmd.last_result = {'arg1': ns.arg1}


class WithCommandSets(ExternalTestMixin, cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""
    def __init__(self, *args, **kwargs):
        super(WithCommandSets, self).__init__(*args, **kwargs)


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

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Also Alone' in cmds_cats
    assert 'durian' in cmds_cats['Also Alone']

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']


def test_custom_construct_commandsets():
    # Verifies that a custom initialized CommandSet loads correctly when passed into the constructor
    command_set = CommandSetB('foo')
    app = WithCommandSets(command_sets=[command_set])

    cmds_cats, cmds_doc, cmds_undoc, help_topics = app._build_command_info()
    assert 'Command Set B' in cmds_cats

    # Verifies that the same CommandSet can not be loaded twice
    command_set_2 = CommandSetB('bar')
    with pytest.raises(ValueError):
        assert app.install_command_set(command_set_2)


def test_load_commands(command_sets_manual):

    # now install a command set and verify the commands are now present
    cmd_set = CommandSetA()
    command_sets_manual.install_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']

    # uninstall the command set and verify it is now also no longer accessible
    command_sets_manual.uninstall_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' not in cmds_cats
    assert 'Fruits' not in cmds_cats

    # reinstall the command set and verify it is accessible
    command_sets_manual.install_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']


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


def test_commandset_decorators(command_sets_app):
    result = command_sets_app.app_cmd('cranberry juice extra1 extra2')
    assert len(result.data['unknown']) == 2
    assert 'extra1' in result.data['unknown']
    assert 'extra2' in result.data['unknown']
    assert result.data['arg1'] == 'juice'
    assert result.stderr is None

    result = command_sets_app.app_cmd('durian juice extra1 extra2')
    assert len(result.data['args']) == 3
    assert 'juice' in result.data['args']
    assert 'extra1' in result.data['args']
    assert 'extra2' in result.data['args']
    assert result.stderr is None

    result = command_sets_app.app_cmd('durian')
    assert len(result.data['args']) == 0
    assert result.stderr is None

    result = command_sets_app.app_cmd('elderberry')
    assert result.stderr is not None
    assert len(result.stderr) > 0
    assert 'arguments are required' in result.stderr
    assert result.data is None

    result = command_sets_app.app_cmd('elderberry a b')
    assert result.stderr is not None
    assert len(result.stderr) > 0
    assert 'unrecognized arguments' in result.stderr
    assert result.data is None

