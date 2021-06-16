# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

import argparse
from typing import (
    List,
)

import pytest

import cmd2
from cmd2 import (
    Settable,
)
from cmd2.exceptions import (
    CommandSetRegistrationError,
)

from .conftest import (
    WithCommandSets,
    complete_tester,
    normalize,
    run_cmd,
)


class CommandSetBase(cmd2.CommandSet):
    pass


@cmd2.with_default_category('Fruits')
class CommandSetA(CommandSetBase):
    def on_register(self, cmd) -> None:
        super().on_register(cmd)
        print("in on_register now")

    def on_registered(self) -> None:
        super().on_registered()
        print("in on_registered now")

    def on_unregister(self) -> None:
        super().on_unregister()
        print("in on_unregister now")

    def on_unregistered(self) -> None:
        super().on_unregistered()
        print("in on_unregistered now")

    def do_apple(self, statement: cmd2.Statement):
        self._cmd.poutput('Apple!')

    def do_banana(self, statement: cmd2.Statement):
        """Banana Command"""
        self._cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser()
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser(cranberry_parser, with_unknown_args=True)
    def do_cranberry(self, ns: argparse.Namespace, unknown: List[str]):
        self._cmd.poutput('Cranberry {}!!'.format(ns.arg1))
        if unknown and len(unknown):
            self._cmd.poutput('Unknown: ' + ', '.join(['{}'] * len(unknown)).format(*unknown))
        self._cmd.last_result = {'arg1': ns.arg1, 'unknown': unknown}

    def help_cranberry(self):
        self._cmd.stdout.write('This command does diddly squat...\n')

    @cmd2.with_argument_list
    @cmd2.with_category('Also Alone')
    def do_durian(self, args: List[str]):
        """Durian Command"""
        self._cmd.poutput('{} Arguments: '.format(len(args)))
        self._cmd.poutput(', '.join(['{}'] * len(args)).format(*args))
        self._cmd.last_result = {'args': args}

    def complete_durian(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return self._cmd.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    elderberry_parser = cmd2.Cmd2ArgumentParser()
    elderberry_parser.add_argument('arg1')

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(elderberry_parser)
    def do_elderberry(self, ns: argparse.Namespace):
        self._cmd.poutput('Elderberry {}!!'.format(ns.arg1))
        self._cmd.last_result = {'arg1': ns.arg1}

    # Test that CommandSet with as_subcommand_to decorator successfully loads
    # during `cmd2.Cmd.__init__()`.
    main_parser = cmd2.Cmd2ArgumentParser(description="Main Command")
    main_subparsers = main_parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')
    main_subparsers.required = True

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(main_parser)
    def do_main(self, args: argparse.Namespace) -> None:
        # Call handler for whatever subcommand was selected
        handler = args.cmd2_handler.get()
        handler(args)

    # main -> sub
    subcmd_parser = cmd2.Cmd2ArgumentParser(description="Sub Command")

    @cmd2.as_subcommand_to('main', 'sub', subcmd_parser, help="sub command")
    def subcmd_func(self, args: argparse.Namespace) -> None:
        self._cmd.poutput("Subcommand Ran")


@cmd2.with_default_category('Command Set B')
class CommandSetB(CommandSetBase):
    def __init__(self, arg1):
        super().__init__()
        self._arg1 = arg1

    def do_aardvark(self, statement: cmd2.Statement):
        self._cmd.poutput('Aardvark!')

    def do_bat(self, statement: cmd2.Statement):
        """Banana Command"""
        self._cmd.poutput('Bat!!')

    def do_crocodile(self, statement: cmd2.Statement):
        self._cmd.poutput('Crocodile!!')


def test_autoload_commands(command_sets_app):
    # verifies that, when autoload is enabled, CommandSets and registered functions all show up

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_app._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']
    assert 'main' in cmds_cats['Alone']

    # Test subcommand was autoloaded
    result = command_sets_app.app_cmd('main sub')
    assert 'Subcommand Ran' in result.stdout

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

    # Verifies that the same CommandSet cannot be loaded twice
    command_set_2 = CommandSetB('bar')
    with pytest.raises(CommandSetRegistrationError):
        assert app.register_command_set(command_set_2)

    # Verify that autoload doesn't conflict with a manually loaded CommandSet that could be autoloaded.
    command_set_a = CommandSetA()
    app2 = WithCommandSets(command_sets=[command_set_a])

    with pytest.raises(CommandSetRegistrationError):
        app2.register_command_set(command_set_b)

    app.unregister_command_set(command_set_b)

    app2.register_command_set(command_set_b)

    assert hasattr(app2, 'do_apple')
    assert hasattr(app2, 'do_aardvark')

    assert app2.find_commandset_for_command('aardvark') is command_set_b
    assert app2.find_commandset_for_command('apple') is command_set_a

    matches = app2.find_commandsets(CommandSetBase, subclass_match=True)
    assert command_set_a in matches
    assert command_set_b in matches
    assert command_set_2 not in matches


def test_load_commands(command_sets_manual, capsys):

    # now install a command set and verify the commands are now present
    cmd_set = CommandSetA()

    assert command_sets_manual.find_commandset_for_command('elderberry') is None
    assert not command_sets_manual.find_commandsets(CommandSetA)

    command_sets_manual.register_command_set(cmd_set)

    assert command_sets_manual.find_commandsets(CommandSetA)[0] is cmd_set
    assert command_sets_manual.find_commandset_for_command('elderberry') is cmd_set

    # Make sure registration callbacks ran
    out, err = capsys.readouterr()
    assert "in on_register now" in out
    assert "in on_registered now" in out

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']
    assert 'main' in cmds_cats['Alone']

    # Test subcommand was loaded
    result = command_sets_manual.app_cmd('main sub')
    assert 'Subcommand Ran' in result.stdout

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']

    # uninstall the command set and verify it is now also no longer accessible
    command_sets_manual.unregister_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' not in cmds_cats
    assert 'Fruits' not in cmds_cats

    # Make sure unregistration callbacks ran
    out, err = capsys.readouterr()
    assert "in on_unregister now" in out
    assert "in on_unregistered now" in out

    # uninstall a second time and verify no errors happen
    command_sets_manual.unregister_command_set(cmd_set)

    # reinstall the command set and verify it is accessible
    command_sets_manual.register_command_set(cmd_set)

    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']
    assert 'main' in cmds_cats['Alone']

    # Test subcommand was loaded
    result = command_sets_manual.app_cmd('main sub')
    assert 'Subcommand Ran' in result.stdout

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']


def test_commandset_decorators(command_sets_app):
    result = command_sets_app.app_cmd('cranberry juice extra1 extra2')
    assert result is not None
    assert result.data is not None
    assert len(result.data['unknown']) == 2
    assert 'extra1' in result.data['unknown']
    assert 'extra2' in result.data['unknown']
    assert result.data['arg1'] == 'juice'
    assert not result.stderr

    result = command_sets_app.app_cmd('durian juice extra1 extra2')
    assert len(result.data['args']) == 3
    assert 'juice' in result.data['args']
    assert 'extra1' in result.data['args']
    assert 'extra2' in result.data['args']
    assert not result.stderr

    result = command_sets_app.app_cmd('durian')
    assert len(result.data['args']) == 0
    assert not result.stderr

    result = command_sets_app.app_cmd('elderberry')
    assert 'arguments are required' in result.stderr
    assert result.data is None

    result = command_sets_app.app_cmd('elderberry a b')
    assert 'unrecognized arguments' in result.stderr
    assert result.data is None


def test_load_commandset_errors(command_sets_manual, capsys):
    cmd_set = CommandSetA()

    # create a conflicting command before installing CommandSet to verify rollback behavior
    command_sets_manual._install_command_function('durian', cmd_set.do_durian)
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.register_command_set(cmd_set)

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
    command_sets_manual.register_command_set(cmd_set)
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
        self._cut_called = False

    cut_parser = cmd2.Cmd2ArgumentParser()
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    def namespace_provider(self) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.cut_called = self._cut_called
        return ns

    @cmd2.with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace):
        """Cut something"""
        handler = ns.cmd2_handler.get()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
            self._cut_called = True
        else:
            # No subcommand was provided, so call help
            self._cmd.pwarning('This command does nothing without sub-parsers registered')
            self._cmd.do_help('cut')

    stir_parser = cmd2.Cmd2ArgumentParser()
    stir_subparsers = stir_parser.add_subparsers(title='item', help='what to stir')

    @cmd2.with_argparser(stir_parser, ns_provider=namespace_provider)
    def do_stir(self, ns: argparse.Namespace):
        """Stir something"""
        if not ns.cut_called:
            self._cmd.poutput('Need to cut before stirring')
            return

        handler = ns.cmd2_handler.get()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            self._cmd.pwarning('This command does nothing without sub-parsers registered')
            self._cmd.do_help('stir')

    stir_pasta_parser = cmd2.Cmd2ArgumentParser()
    stir_pasta_parser.add_argument('--option', '-o')
    stir_pasta_parser.add_subparsers(title='style', help='Stir style')

    @cmd2.as_subcommand_to('stir', 'pasta', stir_pasta_parser)
    def stir_pasta(self, ns: argparse.Namespace):
        handler = ns.cmd2_handler.get()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            self._cmd.poutput('Stir pasta haphazardly')


class LoadableBadBase(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableBadBase, self).__init__()
        self._dummy = dummy  # prevents autoload

    def do_cut(self, ns: argparse.Namespace):
        """Cut something"""
        handler = ns.cmd2_handler.get()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            self._cmd.poutput('This command does nothing without sub-parsers registered')
            self._cmd.do_help('cut')


@cmd2.with_default_category('Fruits')
class LoadableFruits(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableFruits, self).__init__()
        self._dummy = dummy  # prevents autoload

    def do_apple(self, _: cmd2.Statement):
        self._cmd.poutput('Apple')

    banana_parser = cmd2.Cmd2ArgumentParser()
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help='Cut banana', aliases=['bananer'])
    def cut_banana(self, ns: argparse.Namespace):
        """Cut banana"""
        self._cmd.poutput('cutting banana: ' + ns.direction)


class LoadablePastaStir(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadablePastaStir, self).__init__()
        self._dummy = dummy  # prevents autoload

    stir_pasta_vigor_parser = cmd2.Cmd2ArgumentParser()
    stir_pasta_vigor_parser.add_argument('frequency')

    @cmd2.as_subcommand_to('stir pasta', 'vigorously', stir_pasta_vigor_parser)
    def stir_pasta_vigorously(self, ns: argparse.Namespace):
        self._cmd.poutput('stir the pasta vigorously')


@cmd2.with_default_category('Vegetables')
class LoadableVegetables(cmd2.CommandSet):
    def __init__(self, dummy):
        super(LoadableVegetables, self).__init__()
        self._dummy = dummy  # prevents autoload

    def do_arugula(self, _: cmd2.Statement):
        self._cmd.poutput('Arugula')

    def complete_style_arg(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return ['quartered', 'diced']

    bokchoy_parser = cmd2.Cmd2ArgumentParser()
    bokchoy_parser.add_argument('style', completer=complete_style_arg)

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, ns: argparse.Namespace):
        self._cmd.poutput('Bok Choy: ' + ns.style)


def test_subcommands(command_sets_manual):

    base_cmds = LoadableBase(1)
    badbase_cmds = LoadableBadBase(1)
    fruit_cmds = LoadableFruits(1)
    veg_cmds = LoadableVegetables(1)

    # installing subcommands without base command present raises exception
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.register_command_set(fruit_cmds)

    # if the base command is present but isn't an argparse command, expect exception
    command_sets_manual.register_command_set(badbase_cmds)
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.register_command_set(fruit_cmds)

    # verify that the commands weren't installed
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'cut' in cmds_doc
    assert 'Fruits' not in cmds_cats

    # Now install the good base commands
    command_sets_manual.unregister_command_set(badbase_cmds)
    command_sets_manual.register_command_set(base_cmds)

    # verify that we catch an attempt to register subcommands when the commandset isn't installed
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._register_subcommands(fruit_cmds)

    cmd_result = command_sets_manual.app_cmd('cut')
    assert 'This command does nothing without sub-parsers registered' in cmd_result.stderr

    # verify that command set install without problems
    command_sets_manual.register_command_set(fruit_cmds)
    command_sets_manual.register_command_set(veg_cmds)
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
    command_sets_manual.unregister_command_set(fruit_cmds)
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'Fruits' not in cmds_cats

    # verify a double-unregister raises exception
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._unregister_subcommands(fruit_cmds)
    command_sets_manual.unregister_command_set(veg_cmds)

    # Disable command and verify subcommands still load and unload
    command_sets_manual.disable_command('cut', 'disabled for test')

    # verify that command set install without problems
    command_sets_manual.register_command_set(fruit_cmds)
    command_sets_manual.register_command_set(veg_cmds)

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
    command_sets_manual.unregister_command_set(fruit_cmds)
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_manual._build_command_info()
    assert 'Fruits' not in cmds_cats

    # verify a double-unregister raises exception
    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual._unregister_subcommands(fruit_cmds)

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.unregister_command_set(base_cmds)

    command_sets_manual.unregister_command_set(veg_cmds)
    command_sets_manual.unregister_command_set(base_cmds)


def test_nested_subcommands(command_sets_manual):
    base_cmds = LoadableBase(1)
    pasta_cmds = LoadablePastaStir(1)

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.register_command_set(pasta_cmds)

    command_sets_manual.register_command_set(base_cmds)

    command_sets_manual.register_command_set(pasta_cmds)

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.unregister_command_set(base_cmds)

    class BadNestedSubcommands(cmd2.CommandSet):
        def __init__(self, dummy):
            super(BadNestedSubcommands, self).__init__()
            self._dummy = dummy  # prevents autoload

        stir_pasta_vigor_parser = cmd2.Cmd2ArgumentParser()
        stir_pasta_vigor_parser.add_argument('frequency')

        # stir sauce doesn't exist anywhere, this should fail
        @cmd2.as_subcommand_to('stir sauce', 'vigorously', stir_pasta_vigor_parser)
        def stir_pasta_vigorously(self, ns: argparse.Namespace):
            self._cmd.poutput('stir the pasta vigorously')

    with pytest.raises(CommandSetRegistrationError):
        command_sets_manual.register_command_set(BadNestedSubcommands(1))

    fruit_cmds = LoadableFruits(1)
    command_sets_manual.register_command_set(fruit_cmds)

    # validates custom namespace provider works correctly. Stir command will fail until
    # the cut command is called
    result = command_sets_manual.app_cmd('stir pasta vigorously everyminute')
    assert 'Need to cut before stirring' in result.stdout

    result = command_sets_manual.app_cmd('cut banana discs')
    assert 'cutting banana: discs' in result.stdout

    result = command_sets_manual.app_cmd('stir pasta vigorously everyminute')
    assert 'stir the pasta vigorously' in result.stdout


class AppWithSubCommands(cmd2.Cmd):
    """Class for testing usage of `as_subcommand_to` decorator directly in a Cmd2 subclass."""

    def __init__(self, *args, **kwargs):
        super(AppWithSubCommands, self).__init__(*args, **kwargs)

    cut_parser = cmd2.Cmd2ArgumentParser()
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    @cmd2.with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace):
        """Cut something"""
        handler = ns.cmd2_handler.get()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            # No subcommand was provided, so call help
            self.poutput('This command does nothing without sub-parsers registered')
            self.do_help('cut')

    banana_parser = cmd2.Cmd2ArgumentParser()
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help='Cut banana', aliases=['bananer'])
    def cut_banana(self, ns: argparse.Namespace):
        """Cut banana"""
        self.poutput('cutting banana: ' + ns.direction)

    def complete_style_arg(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return ['quartered', 'diced']

    bokchoy_parser = cmd2.Cmd2ArgumentParser()
    bokchoy_parser.add_argument('style', completer=complete_style_arg)

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, _: argparse.Namespace):
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


@cmd2.with_default_category('With Completer')
class WithCompleterCommandSet(cmd2.CommandSet):
    states = ['alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware']

    def __init__(self, dummy):
        """dummy variable prevents this from being autoloaded in other tests"""
        super(WithCompleterCommandSet, self).__init__()

    def complete_states(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        assert self is complete_states_expected_self
        return self._cmd.basic_complete(text, line, begidx, endidx, self.states)


class SubclassCommandSetCase1(WithCompleterCommandSet):
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer=WithCompleterCommandSet.complete_states)

    @cmd2.with_argparser(parser)
    def do_case1(self, ns: argparse.Namespace):
        self._cmd.poutput('something {}'.format(ns.state))


class SubclassCommandSetErrorCase2(WithCompleterCommandSet):
    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer=WithCompleterCommandSet.complete_states)

    @cmd2.with_argparser(parser)
    def do_error2(self, ns: argparse.Namespace):
        self._cmd.poutput('something {}'.format(ns.state))


class SubclassCommandSetCase2(cmd2.CommandSet):
    def __init__(self, dummy):
        """dummy variable prevents this from being autoloaded in other tests"""
        super(SubclassCommandSetCase2, self).__init__()

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer=WithCompleterCommandSet.complete_states)

    @cmd2.with_argparser(parser)
    def do_case2(self, ns: argparse.Namespace):
        self._cmd.poutput('something {}'.format(ns.state))


def test_cross_commandset_completer(command_sets_manual):
    global complete_states_expected_self
    # This tests the different ways to locate the matching CommandSet when completing an argparse argument.
    # Exercises the `_complete_arg` function of `ArgparseCompleter` in `argparse_completer.py`

    ####################################################################################################################
    # This exercises Case 1
    # If the CommandSet holding a command is a sub-class of the class that defines the completer function, then use that
    # CommandSet instance as self when calling the completer
    case1_set = SubclassCommandSetCase1(1)

    command_sets_manual.register_command_set(case1_set)

    text = ''
    line = 'case1 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = case1_set
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert command_sets_manual.completion_matches == WithCompleterCommandSet.states

    assert getattr(command_sets_manual.cmd_func('case1').__func__, cmd2.constants.CMD_ATTR_HELP_CATEGORY) == 'With Completer'

    command_sets_manual.unregister_command_set(case1_set)

    ####################################################################################################################
    # This exercises Case 2
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match

    # First verify that, without the correct command set
    base_set = WithCompleterCommandSet(1)
    case2_set = SubclassCommandSetCase2(2)
    command_sets_manual.register_command_set(base_set)
    command_sets_manual.register_command_set(case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = base_set
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert command_sets_manual.completion_matches == WithCompleterCommandSet.states

    command_sets_manual.unregister_command_set(case2_set)
    command_sets_manual.unregister_command_set(base_set)

    ####################################################################################################################
    # This exercises Case 3
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function,
    # and no exact type match can be found, but sub-class matches can be found and there is only a single
    # subclass match, then use the lone subclass match as the parent CommandSet.

    command_sets_manual.register_command_set(case1_set)
    command_sets_manual.register_command_set(case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = case1_set
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert command_sets_manual.completion_matches == WithCompleterCommandSet.states

    command_sets_manual.unregister_command_set(case2_set)
    command_sets_manual.unregister_command_set(case1_set)

    ####################################################################################################################
    # Error Case 1
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match, none are found
    # search for sub-class matches, also none are found.

    command_sets_manual.register_command_set(case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is None
    assert command_sets_manual.completion_matches == []

    command_sets_manual.unregister_command_set(case2_set)

    ####################################################################################################################
    # Error Case 2
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match, none are found
    # search for sub-class matches, more than 1 is found

    error_case2_set = SubclassCommandSetErrorCase2(4)
    command_sets_manual.register_command_set(case1_set)
    command_sets_manual.register_command_set(case2_set)
    command_sets_manual.register_command_set(error_case2_set)

    text = ''
    line = 'case2 {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is None
    assert command_sets_manual.completion_matches == []

    command_sets_manual.unregister_command_set(case2_set)


class CommandSetWithPathComplete(cmd2.CommandSet):
    def __init__(self, dummy):
        """dummy variable prevents this from being autoloaded in other tests"""
        super(CommandSetWithPathComplete, self).__init__()

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('path', nargs='+', help='paths', completer=cmd2.Cmd.path_complete)

    @cmd2.with_argparser(parser)
    def do_path(self, app: cmd2.Cmd, args):
        app.poutput(args.path)


def test_path_complete(command_sets_manual):
    test_set = CommandSetWithPathComplete(1)

    command_sets_manual.register_command_set(test_set)

    text = ''
    line = 'path {}'.format(text)
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, command_sets_manual)

    assert first_match is not None


def test_bad_subcommand():
    class BadSubcommandApp(cmd2.Cmd):
        """Class for testing usage of `as_subcommand_to` decorator directly in a Cmd2 subclass."""

        def __init__(self, *args, **kwargs):
            super(BadSubcommandApp, self).__init__(*args, **kwargs)

        cut_parser = cmd2.Cmd2ArgumentParser()
        cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

        @cmd2.with_argparser(cut_parser)
        def do_cut(self, ns: argparse.Namespace):
            """Cut something"""
            pass

        banana_parser = cmd2.Cmd2ArgumentParser()
        banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

        @cmd2.as_subcommand_to('cut', 'bad name', banana_parser, help='This should fail')
        def cut_banana(self, ns: argparse.Namespace):
            """Cut banana"""
            self.poutput('cutting banana: ' + ns.direction)

    with pytest.raises(CommandSetRegistrationError):
        app = BadSubcommandApp()


def test_commandset_settables():
    # Define an arbitrary class with some attribute
    class Arbitrary:
        def __init__(self):
            self.some_value = 5

    # Declare a CommandSet with a settable of some arbitrary property
    class WithSettablesA(CommandSetBase):
        def __init__(self):
            super(WithSettablesA, self).__init__()

            self._arbitrary = Arbitrary()
            self._settable_prefix = 'addon'
            self.my_int = 11

            self.add_settable(
                Settable(
                    'arbitrary_value',
                    int,
                    'Some settable value',
                    settable_object=self._arbitrary,
                    settable_attrib_name='some_value',
                )
            )

    # Declare a CommandSet with an empty settable prefix
    class WithSettablesNoPrefix(CommandSetBase):
        def __init__(self):
            super(WithSettablesNoPrefix, self).__init__()

            self._arbitrary = Arbitrary()
            self._settable_prefix = ''
            self.my_int = 11

            self.add_settable(
                Settable(
                    'another_value',
                    float,
                    'Some settable value',
                    settable_object=self._arbitrary,
                    settable_attrib_name='some_value',
                )
            )

    # Declare a commandset with duplicate settable name
    class WithSettablesB(CommandSetBase):
        def __init__(self):
            super(WithSettablesB, self).__init__()

            self._arbitrary = Arbitrary()
            self._settable_prefix = 'some'
            self.my_int = 11

            self.add_settable(
                Settable(
                    'arbitrary_value',
                    int,
                    'Some settable value',
                    settable_object=self._arbitrary,
                    settable_attrib_name='some_value',
                )
            )

    # create the command set and cmd2
    cmdset = WithSettablesA()
    arbitrary2 = Arbitrary()
    app = cmd2.Cmd(command_sets=[cmdset], auto_load_commands=False)
    setattr(app, 'str_value', '')
    app.add_settable(Settable('always_prefix_settables', bool, 'Prefix settables', app))
    app._settables['str_value'] = Settable('str_value', str, 'String value', app)

    assert 'arbitrary_value' in app.settables.keys()
    assert 'always_prefix_settables' in app.settables.keys()
    assert 'str_value' in app.settables.keys()

    # verify the settable shows up
    out, err = run_cmd(app, 'set')
    assert 'arbitrary_value: 5' in out
    out, err = run_cmd(app, 'set arbitrary_value')
    assert out == ['arbitrary_value: 5']

    # change the value and verify the value changed
    out, err = run_cmd(app, 'set arbitrary_value 10')
    expected = """
arbitrary_value - was: 5
now: 10
"""
    assert out == normalize(expected)
    out, err = run_cmd(app, 'set arbitrary_value')
    assert out == ['arbitrary_value: 10']

    # can't add to cmd2 now because commandset already has this settable
    with pytest.raises(KeyError):
        app.add_settable(Settable('arbitrary_value', int, 'This should fail', app))

    cmdset.add_settable(
        Settable('arbitrary_value', int, 'Replaced settable', settable_object=arbitrary2, settable_attrib_name='some_value')
    )

    # Can't add a settable to the commandset that already exists in cmd2
    with pytest.raises(KeyError):
        cmdset.add_settable(Settable('always_prefix_settables', int, 'This should also fail', cmdset))

    # Can't remove a settable from the CommandSet if it is elsewhere and not in the CommandSet
    with pytest.raises(KeyError):
        cmdset.remove_settable('always_prefix_settables')

    # verify registering a commandset with duplicate settable names fails
    cmdset_dupname = WithSettablesB()
    with pytest.raises(CommandSetRegistrationError):
        app.register_command_set(cmdset_dupname)

    # unregister the CommandSet and verify the settable is now gone
    app.unregister_command_set(cmdset)
    out, err = run_cmd(app, 'set')
    assert 'arbitrary_value' not in out
    out, err = run_cmd(app, 'set arbitrary_value')
    expected = """
Parameter 'arbitrary_value' not supported (type 'set' for list of parameters).
"""
    assert err == normalize(expected)

    # Add a commandset with no prefix
    cmdset_nopfx = WithSettablesNoPrefix()
    app.register_command_set(cmdset_nopfx)

    with pytest.raises(ValueError):
        app.always_prefix_settables = True

    app.unregister_command_set(cmdset_nopfx)

    # turn on prefixes and add the commandset back
    app.always_prefix_settables = True

    with pytest.raises(CommandSetRegistrationError):
        app.register_command_set(cmdset_nopfx)

    app.register_command_set(cmdset)

    # Verify the settable is back with the defined prefix.
    assert 'addon.arbitrary_value' in app.settables.keys()

    # rename the prefix and verify that the prefix changes everywhere
    cmdset._settable_prefix = 'some'
    assert 'addon.arbitrary_value' not in app.settables.keys()
    assert 'some.arbitrary_value' in app.settables.keys()

    out, err = run_cmd(app, 'set')
    assert 'some.arbitrary_value: 5' in out
    out, err = run_cmd(app, 'set some.arbitrary_value')
    assert out == ['some.arbitrary_value: 5']

    # verify registering a commandset with duplicate prefix and settable names fails
    with pytest.raises(CommandSetRegistrationError):
        app.register_command_set(cmdset_dupname)

    cmdset_dupname.remove_settable('arbitrary_value')

    app.register_command_set(cmdset_dupname)

    with pytest.raises(KeyError):
        cmdset_dupname.add_settable(
            Settable(
                'arbitrary_value',
                int,
                'Some settable value',
                settable_object=cmdset_dupname._arbitrary,
                settable_attrib_name='some_value',
            )
        )
