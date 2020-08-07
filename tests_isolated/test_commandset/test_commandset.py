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
from .conftest import complete_tester, WithCommandSets
from cmd2.exceptions import CommandSetRegistrationError


class CommandSetBase(cmd2.CommandSet):
    pass


@cmd2.with_default_category('Fruits')
class CommandSetA(CommandSetBase):
    def do_apple(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Apple!')

    def do_banana(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Banana Command"""
        cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser('cranberry')
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser(cranberry_parser, with_unknown_args=True)
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


@cmd2.with_default_category('Command Set B')
class CommandSetB(CommandSetBase):
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


def test_autoload_commands(command_sets_app):
    # verifies that, when autoload is enabled, CommandSets and registered functions all show up

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_app._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Also Alone' in cmds_cats
    assert 'durian' in cmds_cats['Also Alone']

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']

    assert 'Command Set B' not in cmds_cats


def test_custom_construct_commandsets():
    # Verifies that a custom initialized CommandSet loads correctly when passed into the constructor
    command_set_b = CommandSetB('foo')
    app = WithCommandSets(command_sets=[command_set_b])

    cmds_cats, cmds_doc, cmds_undoc, help_topics = app._build_command_info()
    assert 'Command Set B' in cmds_cats

    # Verifies that the same CommandSet can not be loaded twice
    command_set_2 = CommandSetB('bar')
    with pytest.raises(CommandSetRegistrationError):
        assert app.install_command_set(command_set_2)

    # Verify that autoload doesn't conflict with a manually loaded CommandSet that could be autoloaded.
    command_set_a = CommandSetA()
    app2 = WithCommandSets(command_sets=[command_set_a])

    with pytest.raises(CommandSetRegistrationError):
        app2.install_command_set(command_set_b)

    app.uninstall_command_set(command_set_b)

    app2.install_command_set(command_set_b)

    assert hasattr(app2, 'do_apple')
    assert hasattr(app2, 'do_aardvark')

    assert app2.find_commandset_for_command('aardvark') is command_set_b
    assert app2.find_commandset_for_command('apple') is command_set_a

    matches = app2.find_commandsets(CommandSetBase, subclass_match=True)
    assert command_set_a in matches
    assert command_set_b in matches
    assert command_set_2 not in matches


def test_load_commands(command_sets_manual):

    # now install a command set and verify the commands are now present
    cmd_set = CommandSetA()

    assert command_sets_manual.find_commandset_for_command('elderberry') is None
    assert not command_sets_manual.find_commandsets(CommandSetA)

    command_sets_manual.install_command_set(cmd_set)

    assert command_sets_manual.find_commandsets(CommandSetA)[0] is cmd_set
    assert command_sets_manual.find_commandset_for_command('elderberry') is cmd_set

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

    # uninstall a second time and verify no errors happen
    command_sets_manual.uninstall_command_set(cmd_set)

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


def test_load_commandset_errors(command_sets_manual, capsys):
    cmd_set = CommandSetA()

    # create a conflicting command before installing CommandSet to verify rollback behavior
    command_sets_manual._install_command_function('durian', cmd_set.do_durian)
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.install_command_set(cmd_set)

    # verify that the commands weren't installed
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' not in cmds_cats
    assert 'Fruits' not in cmds_cats
    assert not command_sets_manual._installed_command_sets

    delattr(command_sets_manual, 'do_durian')

    # pre-create intentionally conflicting macro and alias names
    command_sets_manual.app_cmd('macro create apple run_pyscript')
    command_sets_manual.app_cmd('alias create banana run_pyscript')

    # now install a command set and verify the commands are now present
    command_sets_manual.install_command_set(cmd_set)
    out, err = capsys.readouterr()

    # verify aliases and macros are deleted with warning if they conflict with a command
    assert "Deleting alias 'banana'" in err
    assert "Deleting macro 'apple'" in err

    # verify duplicate commands are detected
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._install_command_function('banana', cmd_set.do_banana)

    # verify bad command names are detected
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._install_command_function('bad command', cmd_set.do_banana)

    # verify error conflict with existing completer function
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._install_completer_function('durian', cmd_set.complete_durian)

    # verify error conflict with existing help function
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._install_help_function('cranberry', cmd_set.help_cranberry)


class LoadableBase(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableBase, self).__init__()
        self._dummy = dummy  # prevents autoload

    cut_parser = cmd2.Cmd2ArgumentParser('cut')
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    @cmd2.with_argparser(cut_parser)
    def do_cut(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        """Cut something"""
        handler = ns.get_handler()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            cmd.pwarning('This command does nothing without sub-parsers registered')
            cmd.do_help('cut')


    stir_parser = cmd2.Cmd2ArgumentParser('stir')
    stir_subparsers = stir_parser.add_subparsers(title='item', help='what to stir')

    @cmd2.with_argparser(stir_parser)
    def do_stir(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        """Stir something"""
        handler = ns.get_handler()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            cmd.pwarning('This command does nothing without sub-parsers registered')
            cmd.do_help('stir')

    stir_pasta_parser = cmd2.Cmd2ArgumentParser('pasta', add_help=False)
    stir_pasta_parser.add_argument('--option', '-o')
    stir_pasta_parser.add_subparsers(title='style', help='Stir style')

    @cmd2.as_subcommand_to('stir', 'pasta', stir_pasta_parser)
    def stir_pasta(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        handler = ns.get_handler()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            cmd.poutput('Stir pasta haphazardly')


class LoadableBadBase(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableBadBase, self).__init__()
        self._dummy = dummy  # prevents autoload

    def do_cut(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        """Cut something"""
        handler = ns.get_handler()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            cmd.poutput('This command does nothing without sub-parsers registered')
            cmd.do_help('cut')


@cmd2.with_default_category('Fruits')
class LoadableFruits(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableFruits, self).__init__()
        self._dummy = dummy  # prevents autoload

    def do_apple(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Apple')

    banana_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help='Cut banana', aliases=['bananer'])
    def cut_banana(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        """Cut banana"""
        cmd.poutput('cutting banana: ' + ns.direction)


class LoadablePastaStir(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadablePastaStir, self).__init__()
        self._dummy = dummy  # prevents autoload

    stir_pasta_vigor_parser = cmd2.Cmd2ArgumentParser('vigor', add_help=False)
    stir_pasta_vigor_parser.add_argument('frequency')

    @cmd2.as_subcommand_to('stir pasta', 'vigorously', stir_pasta_vigor_parser)
    def stir_pasta_vigorously(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        cmd.poutput('stir the pasta vigorously')


@cmd2.with_default_category('Vegetables')
class LoadableVegetables(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableVegetables, self).__init__()
        self._dummy = dummy  # prevents autoload

    def do_arugula(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Arugula')

    def complete_style_arg(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return ['quartered', 'diced']

    bokchoy_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    bokchoy_parser.add_argument('style', completer_method=complete_style_arg)

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, cmd: cmd2.Cmd, _: cmd2.Statement):
        cmd.poutput('Bok Choy')


def test_subcommands(command_sets_manual):

    base_cmds = LoadableBase(1)
    badbase_cmds = LoadableBadBase(1)
    fruit_cmds = LoadableFruits(1)
    veg_cmds = LoadableVegetables(1)

    # installing subcommands without base command present raises exception
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.install_command_set(fruit_cmds)

    # if the base command is present but isn't an argparse command, expect exception
    command_sets_manual.install_command_set(badbase_cmds)
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.install_command_set(fruit_cmds)

    # verify that the commands weren't installed
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'cut' in cmds_doc
    assert 'Fruits' not in cmds_cats

    # Now install the good base commands
    command_sets_manual.uninstall_command_set(badbase_cmds)
    command_sets_manual.install_command_set(base_cmds)

    # verify that we catch an attempt to register subcommands when the commandset isn't installed
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._register_subcommands(fruit_cmds)

    cmd_result = command_sets_manual.app_cmd('cut')
    assert 'This command does nothing without sub-parsers registered' in cmd_result.stderr

    # verify that command set install without problems
    command_sets_manual.install_command_set(fruit_cmds)
    command_sets_manual.install_command_set(veg_cmds)
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'Fruits' in cmds_cats

    text = ''
    line = 'cut {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is not None
    # check that the alias shows up correctly
    assert ['banana', 'bananer', 'bokchoy'] == command_sets_manual.completion_matches

    cmd_result = command_sets_manual.app_cmd('cut banana discs')
    assert 'cutting banana: discs' in cmd_result.stdout

    text = ''
    line = 'cut bokchoy {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is not None
    # verify that argparse completer in commandset functions correctly
    assert ['diced', 'quartered'] == command_sets_manual.completion_matches

    # verify that command set uninstalls without problems
    command_sets_manual.uninstall_command_set(fruit_cmds)
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'Fruits' not in cmds_cats

    # verify a double-unregister raises exception
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._unregister_subcommands(fruit_cmds)
    command_sets_manual.uninstall_command_set(veg_cmds)

    # Disable command and verify subcommands still load and unload
    command_sets_manual.disable_command('cut', 'disabled for test')

    # verify that command set install without problems
    command_sets_manual.install_command_set(fruit_cmds)
    command_sets_manual.install_command_set(veg_cmds)

    command_sets_manual.enable_command('cut')

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'Fruits' in cmds_cats

    text = ''
    line = 'cut {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is not None
    # check that the alias shows up correctly
    assert ['banana', 'bananer', 'bokchoy'] == command_sets_manual.completion_matches

    text = ''
    line = 'cut bokchoy {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is not None
    # verify that argparse completer in commandset functions correctly
    assert ['diced', 'quartered'] == command_sets_manual.completion_matches

    # disable again and verify can still uninstnall
    command_sets_manual.disable_command('cut', 'disabled for test')

    # verify that command set uninstalls without problems
    command_sets_manual.uninstall_command_set(fruit_cmds)
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'Fruits' not in cmds_cats

    # verify a double-unregister raises exception
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._unregister_subcommands(fruit_cmds)

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.uninstall_command_set(base_cmds)

    command_sets_manual.uninstall_command_set(veg_cmds)
    command_sets_manual.uninstall_command_set(base_cmds)

def test_nested_subcommands(command_sets_manual):
    base_cmds = LoadableBase(1)
    # fruit_cmds = LoadableFruits(1)
    # veg_cmds = LoadableVegetables(1)
    pasta_cmds = LoadablePastaStir(1)

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.install_command_set(pasta_cmds)

    command_sets_manual.install_command_set(base_cmds)

    command_sets_manual.install_command_set(pasta_cmds)

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.uninstall_command_set(base_cmds)

    class BadNestedSubcommands(cmd2.CommandSet):
        def __init__(self, dummy):
            super(BadNestedSubcommands, self).__init__()
            self._dummy = dummy  # prevents autoload

        stir_pasta_vigor_parser = cmd2.Cmd2ArgumentParser('vigor', add_help=False)
        stir_pasta_vigor_parser.add_argument('frequency')

        @cmd2.as_subcommand_to('stir sauce', 'vigorously', stir_pasta_vigor_parser)
        def stir_pasta_vigorously(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
            cmd.poutput('stir the pasta vigorously')

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.install_command_set(BadNestedSubcommands(1))


class AppWithSubCommands(cmd2.Cmd):
    """Class for testing usage of `as_subcommand_to` decorator directly in a Cmd2 subclass."""
    def __init__(self, *args, **kwargs):
        super(AppWithSubCommands, self).__init__(*args, **kwargs)

    cut_parser = cmd2.Cmd2ArgumentParser('cut')
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    @cmd2.with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace):
        """Cut something"""
        handler = ns.get_handler()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            self.poutput('This command does nothing without sub-parsers registered')
            self.do_help('cut')

    banana_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help='Cut banana', aliases=['bananer'])
    def cut_banana(self, ns: argparse.Namespace):
        """Cut banana"""
        self.poutput('cutting banana: ' + ns.direction)

    def complete_style_arg(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return ['quartered', 'diced']

    bokchoy_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    bokchoy_parser.add_argument('style', completer_method=complete_style_arg)

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, _: cmd2.Statement):
        self.poutput('Bok Choy')


@pytest.fixture
def static_subcommands_app():
    app = AppWithSubCommands()
    return app


def test_static_subcommands(static_subcommands_app):
    cmds_cats, cmds_doc, cmds_undoc, help_topics = static_subcommands_app._build_command_info()
    assert 'Fruits' in cmds_cats

    text = ''
    line = 'cut {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, static_subcommands_app)

    assert first_match is not None
    # check that the alias shows up correctly
    assert ['banana', 'bananer', 'bokchoy'] == static_subcommands_app.completion_matches

    text = ''
    line = 'cut bokchoy {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, static_subcommands_app)

    assert first_match is not None
    # verify that argparse completer in commandset functions correctly
    assert ['diced', 'quartered'] == static_subcommands_app.completion_matches


complete_states_expected_self = None


class WithCompleterCommandSet(cmd2.CommandSet):
    states = ['alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware']

    def __init__(self, dummy):
        """dummy variable prevents this from being autoloaded in other tests"""
        super(WithCompleterCommandSet, self).__init__()

    def complete_states(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        assert self is complete_states_expected_self
        return utils.basic_complete(text, line, begidx, endidx, self.states)


class SubclassCommandSetCase1(WithCompleterCommandSet):
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer_method=WithCompleterCommandSet.complete_states)

    @cmd2.with_argparser(parser)
    def do_case1(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        cmd.poutput('something {}'.format(ns.state))


class SubclassCommandSetErrorCase2(WithCompleterCommandSet):
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer_method=WithCompleterCommandSet.complete_states)

    @cmd2.with_argparser(parser)
    def do_error2(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        cmd.poutput('something {}'.format(ns.state))


class SubclassCommandSetCase2(cmd2.CommandSet):
    def __init__(self, dummy):
        """dummy variable prevents this from being autoloaded in other tests"""
        super(SubclassCommandSetCase2, self).__init__()

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer_method=WithCompleterCommandSet.complete_states)

    @cmd2.with_argparser(parser)
    def do_case2(self, cmd: cmd2.Cmd, ns: argparse.Namespace):
        cmd.poutput('something {}'.format(ns.state))


def test_cross_commandset_completer(command_sets_manual):
    global complete_states_expected_self
    # This tests the different ways to locate the matching CommandSet when completing an argparse argument.
    # Exercises the `_complete_for_arg` function of `ArgparseCompleter` in `argparse_completer.py`

    ####################################################################################################################
    # This exercises Case 1
    # If the CommandSet holding a command is a sub-class of the class that defines the completer function, then use that
    # CommandSet instance as self when calling the completer
    case1_set = SubclassCommandSetCase1(1)

    command_sets_manual.install_command_set(case1_set)

    text = ''
    line = 'case1 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = case1_set
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert command_sets_manual.completion_matches == WithCompleterCommandSet.states

    command_sets_manual.uninstall_command_set(case1_set)

    ####################################################################################################################
    # This exercises Case 2
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match

    # First verify that, without the correct command set
    base_set = WithCompleterCommandSet(1)
    case2_set = SubclassCommandSetCase2(2)
    command_sets_manual.install_command_set(base_set)
    command_sets_manual.install_command_set(case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = base_set
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert command_sets_manual.completion_matches == WithCompleterCommandSet.states

    command_sets_manual.uninstall_command_set(case2_set)
    command_sets_manual.uninstall_command_set(base_set)

    ####################################################################################################################
    # This exercises Case 3
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function,
    # and no exact type match can be found, but sub-class matches can be found and there is only a single
    # subclass match, then use the lone subclass match as the parent CommandSet.

    command_sets_manual.install_command_set(case1_set)
    command_sets_manual.install_command_set(case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = case1_set
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert command_sets_manual.completion_matches == WithCompleterCommandSet.states

    command_sets_manual.uninstall_command_set(case2_set)
    command_sets_manual.uninstall_command_set(case1_set)

    ####################################################################################################################
    # Error Case 1
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match, none are found
    # search for sub-class matches, also none are found.

    command_sets_manual.install_command_set(case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is None
    assert command_sets_manual.completion_matches == []

    command_sets_manual.uninstall_command_set(case2_set)

    ####################################################################################################################
    # Error Case 2
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match, none are found
    # search for sub-class matches, more than 1 is found

    error_case2_set = SubclassCommandSetErrorCase2(4)
    command_sets_manual.install_command_set(case1_set)
    command_sets_manual.install_command_set(case2_set)
    command_sets_manual.install_command_set(error_case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is None
    assert command_sets_manual.completion_matches == []

    command_sets_manual.uninstall_command_set(case2_set)


class CommandSetWithPathComplete(cmd2.CommandSet):
    def __init__(self, dummy):
        """dummy variable prevents this from being autoloaded in other tests"""
        super(CommandSetWithPathComplete, self).__init__()

    parser = argparse.ArgumentParser()
    parser.add_argument('path', nargs='+', help='paths', completer_method=cmd2.Cmd.path_complete)

    @cmd2.with_argparser(parser)
    def do_path(self, app: cmd2.Cmd, args):
        app.poutput(args.path)


def test_path_complete(command_sets_manual):
    test_set = CommandSetWithPathComplete(1)

    command_sets_manual.install_command_set(test_set)

    text = ''
    line = 'path {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is not None
