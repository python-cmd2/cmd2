"""Test CommandSet"""

import argparse
import signal

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

    def do_apple(self, statement: cmd2.Statement) -> None:
        self._cmd.poutput('Apple!')

    def do_banana(self, statement: cmd2.Statement) -> None:
        """Banana Command"""
        self._cmd.poutput('Banana!!')

    cranberry_parser = cmd2.Cmd2ArgumentParser()
    cranberry_parser.add_argument('arg1', choices=['lemonade', 'juice', 'sauce'])

    @cmd2.with_argparser(cranberry_parser, with_unknown_args=True)
    def do_cranberry(self, ns: argparse.Namespace, unknown: list[str]) -> None:
        self._cmd.poutput(f'Cranberry {ns.arg1}!!')
        if unknown and len(unknown):
            self._cmd.poutput('Unknown: ' + ', '.join(['{}'] * len(unknown)).format(*unknown))
        self._cmd.last_result = {'arg1': ns.arg1, 'unknown': unknown}

    def help_cranberry(self) -> None:
        self._cmd.stdout.write('This command does diddly squat...\n')

    @cmd2.with_argument_list
    @cmd2.with_category('Also Alone')
    def do_durian(self, args: list[str]) -> None:
        """Durian Command"""
        self._cmd.poutput(f'{len(args)} Arguments: ')
        self._cmd.poutput(', '.join(['{}'] * len(args)).format(*args))
        self._cmd.last_result = {'args': args}

    def complete_durian(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        return self._cmd.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    elderberry_parser = cmd2.Cmd2ArgumentParser()
    elderberry_parser.add_argument('arg1')

    @cmd2.with_category('Alone')
    @cmd2.with_argparser(elderberry_parser)
    def do_elderberry(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput(f'Elderberry {ns.arg1}!!')
        self._cmd.last_result = {'arg1': ns.arg1}

    # Test that CommandSet with as_subcommand_to decorator successfully loads
    # during `cmd2.Cmd.__init__()`.
    main_parser = cmd2.Cmd2ArgumentParser(description="Main Command")
    main_parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND', required=True)

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
    def __init__(self, arg1) -> None:
        super().__init__()
        self._arg1 = arg1

    def do_aardvark(self, statement: cmd2.Statement) -> None:
        self._cmd.poutput('Aardvark!')

    def do_bat(self, statement: cmd2.Statement) -> None:
        """Banana Command"""
        self._cmd.poutput('Bat!!')

    def do_crocodile(self, statement: cmd2.Statement) -> None:
        self._cmd.poutput('Crocodile!!')


def test_autoload_commands(autoload_command_sets_app) -> None:
    # verifies that, when autoload is enabled, CommandSets and registered functions all show up

    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = autoload_command_sets_app._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']
    assert 'main' in cmds_cats['Alone']

    # Test subcommand was autoloaded
    result = autoload_command_sets_app.app_cmd('main sub')
    assert 'Subcommand Ran' in result.stdout

    assert 'Also Alone' in cmds_cats
    assert 'durian' in cmds_cats['Also Alone']

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']

    assert 'Command Set B' not in cmds_cats


def test_command_synonyms() -> None:
    """Test the use of command synonyms in CommandSets"""

    class SynonymCommandSet(cmd2.CommandSet):
        def __init__(self, arg1) -> None:
            super().__init__()
            self._arg1 = arg1

        @cmd2.with_argparser(cmd2.Cmd2ArgumentParser(description="Native Command"))
        def do_builtin(self, _) -> None:
            pass

        # Create a synonym to a command inside of this CommandSet
        do_builtin_synonym = do_builtin

        # Create a synonym to a command outside of this CommandSet with subcommands.
        # This will best test the synonym check in cmd2.Cmd._check_uninstallable() when
        # we unresgister this CommandSet.
        do_alias_synonym = cmd2.Cmd.do_alias

    cs = SynonymCommandSet("foo")
    app = WithCommandSets(command_sets=[cs])

    # Make sure the synonyms have the same parser as what they alias
    builtin_parser = app._command_parsers.get(app.do_builtin)
    builtin_synonym_parser = app._command_parsers.get(app.do_builtin_synonym)
    assert builtin_parser is not None
    assert builtin_parser is builtin_synonym_parser

    alias_parser = app._command_parsers.get(cmd2.Cmd.do_alias)
    alias_synonym_parser = app._command_parsers.get(app.do_alias_synonym)
    assert alias_parser is not None
    assert alias_parser is alias_synonym_parser

    # Unregister the CommandSet and make sure built-in command and synonyms are gone
    app.unregister_command_set(cs)
    assert not hasattr(app, "do_builtin")
    assert not hasattr(app, "do_builtin_synonym")
    assert not hasattr(app, "do_alias_synonym")

    # Make sure the alias command still exists, has the same parser, and works.
    assert alias_parser is app._command_parsers.get(cmd2.Cmd.do_alias)
    out, _err = run_cmd(app, 'alias --help')
    assert normalize(alias_parser.format_help())[0] in out


def test_custom_construct_commandsets() -> None:
    command_set_b = CommandSetB('foo')

    # Verify that _cmd cannot be accessed until CommandSet is registered.
    with pytest.raises(CommandSetRegistrationError) as excinfo:
        command_set_b._cmd.poutput("test")
    assert "is not registered" in str(excinfo.value)

    # Verifies that a custom initialized CommandSet loads correctly when passed into the constructor
    app = WithCommandSets(command_sets=[command_set_b])

    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = app._build_command_info()
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


def test_load_commands(manual_command_sets_app, capsys) -> None:
    # now install a command set and verify the commands are now present
    cmd_set = CommandSetA()

    assert manual_command_sets_app.find_commandset_for_command('elderberry') is None
    assert not manual_command_sets_app.find_commandsets(CommandSetA)

    manual_command_sets_app.register_command_set(cmd_set)

    assert manual_command_sets_app.find_commandsets(CommandSetA)[0] is cmd_set
    assert manual_command_sets_app.find_commandset_for_command('elderberry') is cmd_set

    out = manual_command_sets_app.app_cmd('apple')
    assert 'Apple!' in out.stdout

    # Make sure registration callbacks ran
    out, _err = capsys.readouterr()
    assert "in on_register now" in out
    assert "in on_registered now" in out

    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']
    assert 'main' in cmds_cats['Alone']

    # Test subcommand was loaded
    result = manual_command_sets_app.app_cmd('main sub')
    assert 'Subcommand Ran' in result.stdout

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']

    # uninstall the command set and verify it is now also no longer accessible
    manual_command_sets_app.unregister_command_set(cmd_set)

    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()

    assert 'Alone' not in cmds_cats
    assert 'Fruits' not in cmds_cats

    # Make sure unregistration callbacks ran
    out, _err = capsys.readouterr()
    assert "in on_unregister now" in out
    assert "in on_unregistered now" in out

    # uninstall a second time and verify no errors happen
    manual_command_sets_app.unregister_command_set(cmd_set)

    # reinstall the command set and verify it is accessible
    manual_command_sets_app.register_command_set(cmd_set)

    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']
    assert 'main' in cmds_cats['Alone']

    # Test subcommand was loaded
    result = manual_command_sets_app.app_cmd('main sub')
    assert 'Subcommand Ran' in result.stdout

    assert 'Fruits' in cmds_cats
    assert 'cranberry' in cmds_cats['Fruits']


def test_commandset_decorators(autoload_command_sets_app) -> None:
    result = autoload_command_sets_app.app_cmd('cranberry juice extra1 extra2')
    assert result is not None
    assert result.data is not None
    assert len(result.data['unknown']) == 2
    assert 'extra1' in result.data['unknown']
    assert 'extra2' in result.data['unknown']
    assert result.data['arg1'] == 'juice'
    assert not result.stderr

    result = autoload_command_sets_app.app_cmd('durian juice extra1 extra2')
    assert len(result.data['args']) == 3
    assert 'juice' in result.data['args']
    assert 'extra1' in result.data['args']
    assert 'extra2' in result.data['args']
    assert not result.stderr

    result = autoload_command_sets_app.app_cmd('durian')
    assert len(result.data['args']) == 0
    assert not result.stderr

    result = autoload_command_sets_app.app_cmd('elderberry')
    assert 'arguments are required' in result.stderr
    assert result.data is None

    result = autoload_command_sets_app.app_cmd('elderberry a b')
    assert 'unrecognized arguments' in result.stderr
    assert result.data is None


def test_load_commandset_errors(manual_command_sets_app, capsys) -> None:
    cmd_set = CommandSetA()

    # create a conflicting command before installing CommandSet to verify rollback behavior
    manual_command_sets_app._install_command_function('do_durian', cmd_set.do_durian)
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.register_command_set(cmd_set)

    # verify that the commands weren't installed
    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()

    assert 'Alone' not in cmds_cats
    assert 'Fruits' not in cmds_cats
    assert not manual_command_sets_app._installed_command_sets

    delattr(manual_command_sets_app, 'do_durian')

    # pre-create intentionally conflicting macro and alias names
    manual_command_sets_app.app_cmd('macro create apple run_pyscript')
    manual_command_sets_app.app_cmd('alias create banana run_pyscript')

    # now install a command set and verify the commands are now present
    manual_command_sets_app.register_command_set(cmd_set)
    _out, err = capsys.readouterr()

    # verify aliases and macros are deleted with warning if they conflict with a command
    assert "Deleting alias 'banana'" in err
    assert "Deleting macro 'apple'" in err

    # verify command functions which don't start with "do_" raise an exception
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._install_command_function('new_cmd', cmd_set.do_banana)

    # verify methods which don't start with "do_" raise an exception
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._install_command_function('do_new_cmd', cmd_set.on_register)

    # verify duplicate commands are detected
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._install_command_function('do_banana', cmd_set.do_banana)

    # verify bad command names are detected
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._install_command_function('do_bad command', cmd_set.do_banana)

    # verify error conflict with existing completer function
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._install_completer_function('durian', cmd_set.complete_durian)

    # verify error conflict with existing help function
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._install_help_function('cranberry', cmd_set.help_cranberry)


class LoadableBase(cmd2.CommandSet):
    def __init__(self, dummy) -> None:
        super().__init__()
        self._dummy = dummy  # prevents autoload
        self._cut_called = False

    cut_parser = cmd2.Cmd2ArgumentParser()
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    def namespace_provider(self) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.cut_called = self._cut_called
        return ns

    @cmd2.with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace) -> None:
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
    def do_stir(self, ns: argparse.Namespace) -> None:
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
    def stir_pasta(self, ns: argparse.Namespace) -> None:
        handler = ns.cmd2_handler.get()
        if handler is not None:
            # Call whatever subcommand function was selected
            handler(ns)
        else:
            self._cmd.poutput('Stir pasta haphazardly')


class LoadableBadBase(cmd2.CommandSet):
    def __init__(self, dummy) -> None:
        super().__init__()
        self._dummy = dummy  # prevents autoload

    def do_cut(self, ns: argparse.Namespace) -> None:
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
    def __init__(self, dummy) -> None:
        super().__init__()
        self._dummy = dummy  # prevents autoload

    def do_apple(self, _: cmd2.Statement) -> None:
        self._cmd.poutput('Apple')

    banana_parser = cmd2.Cmd2ArgumentParser()
    banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

    @cmd2.as_subcommand_to('cut', 'banana', banana_parser, help='Cut banana', aliases=['bananer'])
    def cut_banana(self, ns: argparse.Namespace) -> None:
        """Cut banana"""
        self._cmd.poutput('cutting banana: ' + ns.direction)


class LoadablePastaStir(cmd2.CommandSet):
    def __init__(self, dummy) -> None:
        super().__init__()
        self._dummy = dummy  # prevents autoload

    stir_pasta_vigor_parser = cmd2.Cmd2ArgumentParser()
    stir_pasta_vigor_parser.add_argument('frequency')

    @cmd2.as_subcommand_to('stir pasta', 'vigorously', stir_pasta_vigor_parser)
    def stir_pasta_vigorously(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput('stir the pasta vigorously')


@cmd2.with_default_category('Vegetables')
class LoadableVegetables(cmd2.CommandSet):
    def __init__(self, dummy) -> None:
        super().__init__()
        self._dummy = dummy  # prevents autoload

    def do_arugula(self, _: cmd2.Statement) -> None:
        self._cmd.poutput('Arugula')

    def complete_style_arg(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        return ['quartered', 'diced']

    bokchoy_parser = cmd2.Cmd2ArgumentParser()
    bokchoy_parser.add_argument('style', completer=complete_style_arg)

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput('Bok Choy: ' + ns.style)


def test_subcommands(manual_command_sets_app) -> None:
    base_cmds = LoadableBase(1)
    badbase_cmds = LoadableBadBase(1)
    fruit_cmds = LoadableFruits(1)
    veg_cmds = LoadableVegetables(1)

    # installing subcommands without base command present raises exception
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.register_command_set(fruit_cmds)

    # if the base command is present but isn't an argparse command, expect exception
    manual_command_sets_app.register_command_set(badbase_cmds)
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.register_command_set(fruit_cmds)

    # verify that the commands weren't installed
    cmds_cats, cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()
    assert 'cut' in cmds_doc
    assert 'Fruits' not in cmds_cats

    # Now install the good base commands
    manual_command_sets_app.unregister_command_set(badbase_cmds)
    manual_command_sets_app.register_command_set(base_cmds)

    # verify that we catch an attempt to register subcommands when the commandset isn't installed
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._register_subcommands(fruit_cmds)

    cmd_result = manual_command_sets_app.app_cmd('cut')
    assert 'This command does nothing without sub-parsers registered' in cmd_result.stderr

    # verify that command set install without problems
    manual_command_sets_app.register_command_set(fruit_cmds)
    manual_command_sets_app.register_command_set(veg_cmds)
    cmds_cats, cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()
    assert 'Fruits' in cmds_cats

    text = ''
    line = f'cut {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)

    assert first_match is not None
    # check that the alias shows up correctly
    assert manual_command_sets_app.completion_matches == ['banana', 'bananer', 'bokchoy']

    cmd_result = manual_command_sets_app.app_cmd('cut banana discs')
    assert 'cutting banana: discs' in cmd_result.stdout

    text = ''
    line = f'cut bokchoy {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)

    assert first_match is not None
    # verify that argparse completer in commandset functions correctly
    assert manual_command_sets_app.completion_matches == ['diced', 'quartered']

    # verify that command set uninstalls without problems
    manual_command_sets_app.unregister_command_set(fruit_cmds)
    cmds_cats, cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()
    assert 'Fruits' not in cmds_cats

    # verify a double-unregister raises exception
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._unregister_subcommands(fruit_cmds)
    manual_command_sets_app.unregister_command_set(veg_cmds)

    # Disable command and verify subcommands still load and unload
    manual_command_sets_app.disable_command('cut', 'disabled for test')

    # verify that command set install without problems
    manual_command_sets_app.register_command_set(fruit_cmds)
    manual_command_sets_app.register_command_set(veg_cmds)

    manual_command_sets_app.enable_command('cut')

    cmds_cats, cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()
    assert 'Fruits' in cmds_cats

    text = ''
    line = f'cut {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)

    assert first_match is not None
    # check that the alias shows up correctly
    assert manual_command_sets_app.completion_matches == ['banana', 'bananer', 'bokchoy']

    text = ''
    line = f'cut bokchoy {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)

    assert first_match is not None
    # verify that argparse completer in commandset functions correctly
    assert manual_command_sets_app.completion_matches == ['diced', 'quartered']

    # disable again and verify can still uninstnall
    manual_command_sets_app.disable_command('cut', 'disabled for test')

    # verify that command set uninstalls without problems
    manual_command_sets_app.unregister_command_set(fruit_cmds)
    cmds_cats, cmds_doc, _cmds_undoc, _help_topics = manual_command_sets_app._build_command_info()
    assert 'Fruits' not in cmds_cats

    # verify a double-unregister raises exception
    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app._unregister_subcommands(fruit_cmds)

    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.unregister_command_set(base_cmds)

    manual_command_sets_app.unregister_command_set(veg_cmds)
    manual_command_sets_app.unregister_command_set(base_cmds)


def test_commandset_sigint(manual_command_sets_app) -> None:
    # shows that the command is able to continue execution if the sigint_handler
    # returns True that we've handled interrupting the command.
    class SigintHandledCommandSet(cmd2.CommandSet):
        def do_foo(self, _) -> None:
            self._cmd.poutput('in foo')
            self._cmd.sigint_handler(signal.SIGINT, None)
            self._cmd.poutput('end of foo')

        def sigint_handler(self) -> bool:
            return True

    cs1 = SigintHandledCommandSet()
    manual_command_sets_app.register_command_set(cs1)
    out = manual_command_sets_app.app_cmd('foo')
    assert 'in foo' in out.stdout
    assert 'end of foo' in out.stdout

    # shows that the command is interrupted if we don't report we've handled the sigint
    class SigintUnhandledCommandSet(cmd2.CommandSet):
        def do_bar(self, _) -> None:
            self._cmd.poutput('in do bar')
            self._cmd.sigint_handler(signal.SIGINT, None)
            self._cmd.poutput('end of do bar')

    cs2 = SigintUnhandledCommandSet()
    manual_command_sets_app.register_command_set(cs2)
    out = manual_command_sets_app.app_cmd('bar')
    assert 'in do bar' in out.stdout
    assert 'end of do bar' not in out.stdout


def test_nested_subcommands(manual_command_sets_app) -> None:
    base_cmds = LoadableBase(1)
    pasta_cmds = LoadablePastaStir(1)

    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.register_command_set(pasta_cmds)

    manual_command_sets_app.register_command_set(base_cmds)

    manual_command_sets_app.register_command_set(pasta_cmds)

    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.unregister_command_set(base_cmds)

    class BadNestedSubcommands(cmd2.CommandSet):
        def __init__(self, dummy) -> None:
            super().__init__()
            self._dummy = dummy  # prevents autoload

        stir_pasta_vigor_parser = cmd2.Cmd2ArgumentParser()
        stir_pasta_vigor_parser.add_argument('frequency')

        # stir sauce doesn't exist anywhere, this should fail
        @cmd2.as_subcommand_to('stir sauce', 'vigorously', stir_pasta_vigor_parser)
        def stir_pasta_vigorously(self, ns: argparse.Namespace) -> None:
            self._cmd.poutput('stir the pasta vigorously')

    with pytest.raises(CommandSetRegistrationError):
        manual_command_sets_app.register_command_set(BadNestedSubcommands(1))

    fruit_cmds = LoadableFruits(1)
    manual_command_sets_app.register_command_set(fruit_cmds)

    # validates custom namespace provider works correctly. Stir command will fail until
    # the cut command is called
    result = manual_command_sets_app.app_cmd('stir pasta vigorously everyminute')
    assert 'Need to cut before stirring' in result.stdout

    result = manual_command_sets_app.app_cmd('cut banana discs')
    assert 'cutting banana: discs' in result.stdout

    result = manual_command_sets_app.app_cmd('stir pasta vigorously everyminute')
    assert 'stir the pasta vigorously' in result.stdout


class AppWithSubCommands(cmd2.Cmd):
    """Class for testing usage of `as_subcommand_to` decorator directly in a Cmd2 subclass."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    cut_parser = cmd2.Cmd2ArgumentParser()
    cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

    @cmd2.with_argparser(cut_parser)
    def do_cut(self, ns: argparse.Namespace) -> None:
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
    def cut_banana(self, ns: argparse.Namespace) -> None:
        """Cut banana"""
        self.poutput('cutting banana: ' + ns.direction)

    def complete_style_arg(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        return ['quartered', 'diced']

    bokchoy_parser = cmd2.Cmd2ArgumentParser()
    bokchoy_parser.add_argument('style', completer=complete_style_arg)

    @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
    def cut_bokchoy(self, _: argparse.Namespace) -> None:
        self.poutput('Bok Choy')


@pytest.fixture
def static_subcommands_app():
    return AppWithSubCommands(auto_load_commands=True)


def test_static_subcommands(static_subcommands_app) -> None:
    cmds_cats, _cmds_doc, _cmds_undoc, _help_topics = static_subcommands_app._build_command_info()
    assert 'Fruits' in cmds_cats

    text = ''
    line = f'cut {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, static_subcommands_app)

    assert first_match is not None
    # check that the alias shows up correctly
    assert static_subcommands_app.completion_matches == ['banana', 'bananer', 'bokchoy']

    text = ''
    line = f'cut bokchoy {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, static_subcommands_app)

    assert first_match is not None
    # verify that argparse completer in commandset functions correctly
    assert static_subcommands_app.completion_matches == ['diced', 'quartered']


complete_states_expected_self = None


@cmd2.with_default_category('With Completer')
class SupportFuncProvider(cmd2.CommandSet):
    """CommandSet which provides a support function (complete_states) to other CommandSets"""

    states = ('alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware')

    def __init__(self, dummy) -> None:
        """Dummy variable prevents this from being autoloaded in other tests"""
        super().__init__()

    def complete_states(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        assert self is complete_states_expected_self
        return self._cmd.basic_complete(text, line, begidx, endidx, self.states)


class SupportFuncUserSubclass1(SupportFuncProvider):
    """A sub-class of SupportFuncProvider which uses its support function"""

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer=SupportFuncProvider.complete_states)

    @cmd2.with_argparser(parser)
    def do_user_sub1(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput(f'something {ns.state}')


class SupportFuncUserSubclass2(SupportFuncProvider):
    """A second sub-class of SupportFuncProvider which uses its support function"""

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer=SupportFuncProvider.complete_states)

    @cmd2.with_argparser(parser)
    def do_user_sub2(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput(f'something {ns.state}')


class SupportFuncUserUnrelated(cmd2.CommandSet):
    """A CommandSet that isn't related to SupportFuncProvider which uses its support function"""

    def __init__(self, dummy) -> None:
        """Dummy variable prevents this from being autoloaded in other tests"""
        super().__init__()

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('state', type=str, completer=SupportFuncProvider.complete_states)

    @cmd2.with_argparser(parser)
    def do_user_unrelated(self, ns: argparse.Namespace) -> None:
        self._cmd.poutput(f'something {ns.state}')


def test_cross_commandset_completer(manual_command_sets_app, capsys) -> None:
    global complete_states_expected_self  # noqa: PLW0603
    # This tests the different ways to locate the matching CommandSet when completing an argparse argument.
    # Exercises the 3 cases in cmd2.Cmd._resolve_func_self() which is called during argparse tab completion.

    # Create all the CommandSets for these tests
    func_provider = SupportFuncProvider(1)
    user_sub1 = SupportFuncUserSubclass1(2)
    user_sub2 = SupportFuncUserSubclass2(3)
    user_unrelated = SupportFuncUserUnrelated(4)

    ####################################################################################################################
    # This exercises Case 1
    # If the CommandSet holding a command is a sub-class of the class that defines the completer function, then use that
    # CommandSet instance as self when calling the completer

    # Create instances of two different sub-class types to ensure no one removes the case 1 check in Cmd._resolve_func_self().
    # If that check is removed, testing with only 1 sub-class type will still pass. Testing it with two sub-class types
    # will fail and show that the case 1 check cannot be removed.
    manual_command_sets_app.register_command_set(user_sub1)
    manual_command_sets_app.register_command_set(user_sub2)

    text = ''
    line = f'user_sub1 {text}'
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = user_sub1
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert manual_command_sets_app.completion_matches == list(SupportFuncProvider.states)

    assert (
        getattr(manual_command_sets_app.cmd_func('user_sub1').__func__, cmd2.constants.CMD_ATTR_HELP_CATEGORY)
        == 'With Completer'
    )

    manual_command_sets_app.unregister_command_set(user_sub2)
    manual_command_sets_app.unregister_command_set(user_sub1)

    ####################################################################################################################
    # This exercises Case 2
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match

    manual_command_sets_app.register_command_set(func_provider)
    manual_command_sets_app.register_command_set(user_unrelated)

    text = ''
    line = f'user_unrelated {text}'
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = func_provider
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert manual_command_sets_app.completion_matches == list(SupportFuncProvider.states)

    manual_command_sets_app.unregister_command_set(user_unrelated)
    manual_command_sets_app.unregister_command_set(func_provider)

    ####################################################################################################################
    # This exercises Case 3
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function,
    # and no exact type match can be found, but sub-class matches can be found and there is only a single
    # sub-class match, then use the lone sub-class match as the parent CommandSet.

    manual_command_sets_app.register_command_set(user_sub1)
    manual_command_sets_app.register_command_set(user_unrelated)

    text = ''
    line = f'user_unrelated {text}'
    endidx = len(line)
    begidx = endidx
    complete_states_expected_self = user_sub1
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)
    complete_states_expected_self = None

    assert first_match == 'alabama'
    assert manual_command_sets_app.completion_matches == list(SupportFuncProvider.states)

    manual_command_sets_app.unregister_command_set(user_unrelated)
    manual_command_sets_app.unregister_command_set(user_sub1)

    ####################################################################################################################
    # Error Case 1
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match, none are found
    # search for sub-class matches, also none are found.

    manual_command_sets_app.register_command_set(user_unrelated)

    text = ''
    line = f'user_unrelated {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)
    out, _err = capsys.readouterr()

    assert first_match is None
    assert manual_command_sets_app.completion_matches == []
    assert "Could not find CommandSet instance" in out

    manual_command_sets_app.unregister_command_set(user_unrelated)

    ####################################################################################################################
    # Error Case 2
    # If the CommandSet holding a command is unrelated to the CommandSet holding the completer function, then search
    # all installed CommandSet instances for one that is an exact type match, none are found
    # search for sub-class matches, more than 1 is found.

    manual_command_sets_app.register_command_set(user_sub1)
    manual_command_sets_app.register_command_set(user_sub2)
    manual_command_sets_app.register_command_set(user_unrelated)

    text = ''
    line = f'user_unrelated {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)
    out, _err = capsys.readouterr()

    assert first_match is None
    assert manual_command_sets_app.completion_matches == []
    assert "Could not find CommandSet instance" in out

    manual_command_sets_app.unregister_command_set(user_unrelated)
    manual_command_sets_app.unregister_command_set(user_sub2)
    manual_command_sets_app.unregister_command_set(user_sub1)


class CommandSetWithPathComplete(cmd2.CommandSet):
    def __init__(self, dummy) -> None:
        """Dummy variable prevents this from being autoloaded in other tests"""
        super().__init__()

    parser = cmd2.Cmd2ArgumentParser()
    parser.add_argument('path', nargs='+', help='paths', completer=cmd2.Cmd.path_complete)

    @cmd2.with_argparser(parser)
    def do_path(self, app: cmd2.Cmd, args) -> None:
        app.poutput(args.path)


def test_path_complete(manual_command_sets_app) -> None:
    test_set = CommandSetWithPathComplete(1)

    manual_command_sets_app.register_command_set(test_set)

    text = ''
    line = f'path {text}'
    endidx = len(line)
    begidx = endidx
    first_match = complete_tester(text, line, begidx, endidx, manual_command_sets_app)

    assert first_match is not None


def test_bad_subcommand() -> None:
    class BadSubcommandApp(cmd2.Cmd):
        """Class for testing usage of `as_subcommand_to` decorator directly in a Cmd2 subclass."""

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)

        cut_parser = cmd2.Cmd2ArgumentParser()
        cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

        @cmd2.with_argparser(cut_parser)
        def do_cut(self, ns: argparse.Namespace) -> None:
            """Cut something"""

        banana_parser = cmd2.Cmd2ArgumentParser()
        banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

        @cmd2.as_subcommand_to('cut', 'bad name', banana_parser, help='This should fail')
        def cut_banana(self, ns: argparse.Namespace) -> None:
            """Cut banana"""
            self.poutput('cutting banana: ' + ns.direction)

    with pytest.raises(CommandSetRegistrationError):
        BadSubcommandApp()


def test_commandset_settables() -> None:
    # Define an arbitrary class with some attribute
    class Arbitrary:
        def __init__(self) -> None:
            self.some_value = 5

    # Declare a CommandSet with a settable of some arbitrary property
    class WithSettablesA(CommandSetBase):
        def __init__(self) -> None:
            super().__init__()

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
        def __init__(self) -> None:
            super().__init__()

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
        def __init__(self) -> None:
            super().__init__()

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
    app.str_value = ''
    app.add_settable(Settable('always_prefix_settables', bool, 'Prefix settables', app))
    app._settables['str_value'] = Settable('str_value', str, 'String value', app)

    assert 'arbitrary_value' in app.settables
    assert 'always_prefix_settables' in app.settables
    assert 'str_value' in app.settables

    # verify the settable shows up
    out, err = run_cmd(app, 'set')
    any('arbitrary_value' in line and '5' in line for line in out)

    out, err = run_cmd(app, 'set arbitrary_value')
    any('arbitrary_value' in line and '5' in line for line in out)

    # change the value and verify the value changed
    out, err = run_cmd(app, 'set arbitrary_value 10')
    expected = """
arbitrary_value - was: 5
now: 10
"""
    assert out == normalize(expected)
    out, err = run_cmd(app, 'set arbitrary_value')
    any('arbitrary_value' in line and '10' in line for line in out)

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

    with pytest.raises(
        ValueError,
        match=r"Cannot force settable prefixes. CommandSet WithSettablesNoPrefix does not have a settable prefix defined.",
    ):
        app.always_prefix_settables = True

    app.unregister_command_set(cmdset_nopfx)

    # turn on prefixes and add the commandset back
    app.always_prefix_settables = True

    with pytest.raises(CommandSetRegistrationError):
        app.register_command_set(cmdset_nopfx)

    app.register_command_set(cmdset)

    # Verify the settable is back with the defined prefix.
    assert 'addon.arbitrary_value' in app.settables

    # rename the prefix and verify that the prefix changes everywhere
    cmdset._settable_prefix = 'some'
    assert 'addon.arbitrary_value' not in app.settables
    assert 'some.arbitrary_value' in app.settables

    out, err = run_cmd(app, 'set')
    any('some.arbitrary_value' in line and '5' in line for line in out)

    out, err = run_cmd(app, 'set some.arbitrary_value')
    any('some.arbitrary_value' in line and '5' in line for line in out)

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


class NsProviderSet(cmd2.CommandSet):
    # CommandSet which implements a namespace provider
    def __init__(self, dummy) -> None:
        # Use dummy argument so this won't be autoloaded by other tests
        super().__init__()

    def ns_provider(self) -> argparse.Namespace:
        ns = argparse.Namespace()
        # Save what was passed as self from with_argparser().
        ns.self = self
        return ns


class NsProviderApp(cmd2.Cmd):
    # Used to test namespace providers in CommandSets
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        super().__init__(*args, **kwargs)

    @cmd2.with_argparser(cmd2.Cmd2ArgumentParser(), ns_provider=NsProviderSet.ns_provider)
    def do_test_ns(self, args: argparse.Namespace) -> None:
        # Save args.self so the unit tests can read it.
        self.last_result = args.self


def test_ns_provider() -> None:
    """This exercises code in with_argparser() decorator that calls namespace providers"""
    ns_provider_set = NsProviderSet(1)
    app = NsProviderApp(auto_load_commands=False)

    # First test the case in which a namespace provider function resides in a CommandSet class which is registered.
    # with_argparser() will pass the CommandSet instance to the ns_provider() function.
    app.register_command_set(ns_provider_set)
    run_cmd(app, "test_ns")
    assert app.last_result == ns_provider_set

    # Now test the case in which a namespace provider function resides in a CommandSet class which is not registered.
    # with_argparser() will receive None from cmd2.Cmd._resolve_func_self() and therefore pass app as self to ns_provider().
    app.unregister_command_set(ns_provider_set)
    run_cmd(app, "test_ns")
    assert app.last_result == app
