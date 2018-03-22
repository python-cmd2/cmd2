# coding=utf-8
"""
Unit/functional testing for readline tab-completion functions in the cmd2.py module.

These are primarily tests related to readline completer functions which handle tab-completion of cmd2/cmd commands,
file system paths, and shell commands.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import argparse
import os
import sys

import cmd2
import mock
import pytest

from cmd2 import path_complete, basic_complete, flag_based_complete, index_based_complete

# Prefer statically linked gnureadline if available (for macOS compatibility due to issues with libedit)
try:
    import gnureadline as readline
except ImportError:
    # Try to import readline, but allow failure for convenience in Windows unit testing
    # Note: If this actually fails, you should install readline on Linux or Mac or pyreadline on Windows
    try:
        # noinspection PyUnresolvedReferences
        import readline
    except ImportError:
        pass


@pytest.fixture
def cmd2_app():
    c = cmd2.Cmd()
    return c

def complete_tester(text, line, begidx, endidx, app):
    """
    This is a convenience function to test cmd2.complete() since
    in a unit test environment there is no actual console readline
    is monitoring. Therefore we use mock to provide readline data
    to complete().

    :param text: str - the string prefix we are attempting to match
    :param line: str - the current input line with leading whitespace removed
    :param begidx: int - the beginning index of the prefix text
    :param endidx: int - the ending index of the prefix text
    :param app: the cmd2 app that will run completions
    :return: The first matched string or None if there are no matches
             Matches are stored in app.completion_matches
             These matches have been sorted by complete()
    """
    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    first_match = None
    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = app.complete(text, 0)

    return first_match


def test_cmd2_command_completion_single(cmd2_app):
    text = 'he'
    line = 'he'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_complete_command_single(cmd2_app):
    text = 'he'
    line = 'he'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == ['help ']

def test_complete_empty_arg(cmd2_app):
    text = ''
    line = 'help '
    endidx = len(line)
    begidx = endidx - len(text)

    # These matches would normally be sorted by complete()
    expected = cmd2_app.complete_help(text, line, begidx, endidx)
    expected.sort()

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)

    assert first_match is not None and \
        cmd2_app.completion_matches == expected

def test_complete_bogus_command(cmd2_app):
    text = ''
    line = 'fizbuzz '
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None


def test_cmd2_command_completion_single(cmd2_app):
    text = 'hel'
    line = 'help'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_cmd2_command_completion_multiple(cmd2_app):
    text = 'h'
    line = 'h'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_command_completion_nomatch(cmd2_app):
    text = 'fakecommand'
    line = 'fakecommand'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == []


def test_cmd2_help_completion_single(cmd2_app):
    text = 'he'
    line = 'help he'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_help(text, line, begidx, endidx) == ['help']

def test_cmd2_help_completion_multiple(cmd2_app):
    text = 'h'
    line = 'help h'
    endidx = len(line)
    begidx = endidx - len(text)

    # These matches would normally be sorted by complete()
    matches = cmd2_app.complete_help(text, line, begidx, endidx)
    matches.sort()

    assert matches == ['help', 'history']

def test_cmd2_help_completion_nomatch(cmd2_app):
    text = 'fakecommand'
    line = 'help fakecommand'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_help(text, line, begidx, endidx) == []


def test_complete_cursor_by_closing_quote(cmd2_app):
    text = ''
    line = 'fake ""'
    endidx = len(line)
    begidx = endidx - len(text)

    # If the cursor is right after a closing quote, then a space is returned
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == [' ']


def test_shell_command_completion(cmd2_app):
    if sys.platform == "win32":
        text = 'calc'
        expected = ['calc.exe']
    else:
        text = 'egr'
        expected = ['egrep']

    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == expected

def test_shell_command_completion_doesnt_match_wildcards(cmd2_app):
    if sys.platform == "win32":
        text = 'c*'
    else:
        text = 'e*'

    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_multiple(cmd2_app):
    if sys.platform == "win32":
        text = 'c'
        expected = 'calc.exe'
    else:
        text = 'l'
        expected = 'ls'

    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert expected in cmd2_app.complete_shell(text, line, begidx, endidx)

def test_shell_command_completion_nomatch(cmd2_app):
    text = 'zzzz'
    line = 'shell zzzz'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_doesnt_complete_when_just_shell(cmd2_app):
    text = ''
    line = 'shell'
    endidx = len(line)
    begidx = 0
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_does_path_completion_when_after_command(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.complete_shell(text, line, begidx, endidx) == [text + '.py']


def test_path_completion_single_end(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == [text + '.py']

def test_path_completion_multiple(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'cript.py', text + 'cript.txt', text + 'cripts' + os.path.sep]
    expected.sort()

    # These matches would normally be sorted by complete()
    matches = path_complete(text, line, begidx, endidx)
    matches.sort()

    assert expected == matches

def test_path_completion_nomatch(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'fakepath')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == []


def test_default_to_shell_completion(cmd2_app, request):
    cmd2_app.default_to_shell = True
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')

    if sys.platform == "win32":
        command = 'calc.exe'
    else:
        command = 'egrep'

    # Make sure the command is on the testing system
    assert command in cmd2.Cmd._get_exes_in_path(command)
    line = '{} {}'.format(command, text)

    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == [text + '.py ']


def test_path_completion_cwd():
    # Run path complete with no search text
    text = ''
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_no_text = path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    text = os.getcwd() + os.path.sep
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # We have to strip off the text from the beginning since the matches are entire paths
    completions_cwd = [match.replace(text, '', 1) for match in path_complete(text, line, begidx, endidx)]

    # Verify that the first test gave results for entries in the cwd
    assert completions_no_text == completions_cwd
    assert completions_cwd

def test_path_completion_doesnt_match_wildcards(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c*')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    # Currently path completion doesn't accept wildcards, so will always return empty results
    assert path_complete(text, line, begidx, endidx) == []

def test_path_completion_invalid_syntax():
    # Test a missing separator between a ~ and path
    text = '~Desktop'
    line = 'shell fake {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == []

def test_path_completion_just_tilde():
    # Run path with just a tilde
    text = '~'
    line = 'shell fake {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_tilde = path_complete(text, line, begidx, endidx)

    # Path complete should complete the tilde with a slash
    assert completions_tilde == [text + os.path.sep]

def test_path_completion_user_expansion():
    # Run path with a tilde and a slash
    if sys.platform.startswith('win'):
        cmd = 'dir'
    else:
        cmd = 'ls'

    # Use a ~ which will be expanded into the user's home directory
    text = '~{}'.format(os.path.sep)
    line = 'shell {} {}'.format(cmd, text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_tilde_slash = [match.replace(text, '', 1) for match in path_complete(text, line, begidx, endidx)]

    # Run path complete on the user's home directory
    text = os.path.expanduser('~') + os.path.sep
    line = 'shell {} {}'.format(cmd, text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_home = [match.replace(text, '', 1) for match in path_complete(text, line, begidx, endidx)]

    assert completions_tilde_slash == completions_home

def test_path_completion_directories_only(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'cripts' + os.path.sep]

    assert path_complete(text, line, begidx, endidx, dir_only=True) == expected


# List of strings used with basic, flag, and index based completion functions
food_item_strs = ['Pizza', 'Hamburger', 'Ham', 'Potato']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football']

# Dictionary used with flag based completion functions
flag_dict = \
    {
        '-f': food_item_strs,        # Tab-complete food items after -f flag in command line
        '--food': food_item_strs,    # Tab-complete food items after --food flag in command line
        '-s': sport_item_strs,       # Tab-complete sport items after -s flag in command line
        '--sport': sport_item_strs,  # Tab-complete sport items after --sport flag in command line
        '-o': path_complete,         # Tab-complete using path_complete function after -o flag in command line
        '--other': path_complete,    # Tab-complete using path_complete function after --other flag in command line
    }

def test_basic_completion_single():
    text = 'Pi'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert basic_complete(text, line, begidx, endidx, food_item_strs) == ['Pizza']

def test_basic_completion_multiple():
    text = ''
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # These matches would normally be sorted by complete()
    matches = basic_complete(text, line, begidx, endidx, food_item_strs)
    matches.sort()

    assert matches == sorted(food_item_strs)

def test_basic_completion_nomatch():
    text = 'q'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert basic_complete(text, line, begidx, endidx, food_item_strs) == []


def test_flag_based_completion_single():
    text = 'Pi'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == ['Pizza']

def test_flag_based_completion_multiple():
    text = ''
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # These matches would normally be sorted by complete()
    matches = flag_based_complete(text, line, begidx, endidx, flag_dict)
    matches.sort()

    assert matches == sorted(food_item_strs)

def test_flag_based_completion_nomatch():
    text = 'q'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == []

def test_flag_based_default_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'list_food {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict, path_complete) == [text + 'onftest.py']

def test_flag_based_callable_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'list_food -o {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict, path_complete) == [text + 'onftest.py']


# Dictionary used with index based completion functions
index_dict = \
    {
        1: food_item_strs,   # Tab-complete food items at index 1 in command line
        2: sport_item_strs,  # Tab-complete sport items at index 2 in command line
        3: path_complete,    # Tab-complete using path_complete function at index 3 in command line
    }

def test_index_based_completion_single():
    text = 'Foo'
    line = 'command Pizza {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict) == ['Football']

def test_index_based_completion_multiple():
    text = ''
    line = 'command Pizza {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # These matches would normally be sorted by complete()
    matches = index_based_complete(text, line, begidx, endidx, index_dict)
    matches.sort()

    assert matches == sorted(sport_item_strs)

def test_index_based_completion_nomatch():
    text = 'q'
    line = 'command {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert index_based_complete(text, line, begidx, endidx, index_dict) == []

def test_index_based_default_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'command Pizza Bat Computer {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict, path_complete) == [text + 'onftest.py']

def test_index_based_callable_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'command Pizza Bat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict) == [text + 'onftest.py']


def test_parseline_command_and_args(cmd2_app):
    line = 'help history'
    command, args, out_line = cmd2_app.parseline(line)
    assert command == 'help'
    assert args == 'history'
    assert line == out_line

def test_parseline_emptyline(cmd2_app):
    line = ''
    command, args, out_line = cmd2_app.parseline(line)
    assert command is None
    assert args is None
    assert line is out_line

def test_parseline_strips_line(cmd2_app):
    line = '  help history  '
    command, args, out_line = cmd2_app.parseline(line)
    assert command == 'help'
    assert args == 'history'
    assert line.strip() == out_line

def test_parseline_expands_shortcuts(cmd2_app):
    line = '!cat foobar.txt'
    command, args, out_line = cmd2_app.parseline(line)
    assert command == 'shell'
    assert args == 'cat foobar.txt'
    assert line.replace('!', 'shell ') == out_line


class SubcommandsExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""

    def __init__(self):
        cmd2.Cmd.__init__(self)

    # sub-command functions for the base command
    def base_foo(self, args):
        """foo subcommand of base command"""
        self.poutput(args.x * args.y)

    def base_bar(self, args):
        """bar subcommand of base command"""
        self.poutput('((%s))' % args.z)

    # create the top-level parser for the base command
    base_parser = argparse.ArgumentParser(prog='base')
    base_subparsers = base_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" sub-command
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.set_defaults(func=base_foo)

    # create the parser for the "bar" sub-command
    parser_bar = base_subparsers.add_parser('bar', help='bar help')
    parser_bar.add_argument('z', help='string')
    parser_bar.set_defaults(func=base_bar)

    @cmd2.with_argparser(base_parser)
    def do_base(self, args):
        """Base command help"""
        if args.func is not None:
            # Call whatever sub-command function was selected
            args.func(self, args)
        else:
            # No sub-command was provided, so as called
            self.do_help('base')


@pytest.fixture
def sc_app():
    app = SubcommandsExample()
    return app


def test_cmd2_subcommand_completion_single_end(sc_app):
    text = 'f'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and sc_app.completion_matches == ['foo ']

def test_cmd2_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is not None and sc_app.completion_matches == ['bar', 'foo']

def test_cmd2_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is None


def test_cmd2_help_subcommand_completion_single(sc_app):
    text = 'base'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert sc_app.complete_help(text, line, begidx, endidx) == ['base']

def test_cmd2_help_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # These matches would normally be sorted by complete()
    matches = sc_app.complete_help(text, line, begidx, endidx)
    matches.sort()

    assert matches == ['bar', 'foo']


def test_cmd2_help_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert sc_app.complete_help(text, line, begidx, endidx) == []


class SecondLevel(cmd2.Cmd):
    """To be used as a second level command class. """

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = '2ndLevel '

    def do_foo(self, line):
        self.poutput("You called a command in SecondLevel with '%s'. " % line)

    def help_foo(self):
        self.poutput("This is a second level menu. Options are qwe, asd, zxc")

    def complete_foo(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]


second_level_cmd = SecondLevel()


@cmd2.AddSubmenu(second_level_cmd,
                 command='second',
                 require_predefined_shares=False)
class SubmenuApp(cmd2.Cmd):
    """To be used as the main / top level command class that will contain other submenus."""

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = 'TopLevel '


@pytest.fixture
def sb_app():
    app = SubmenuApp()
    return app


def test_cmd2_submenu_completion_single_end(sb_app):
    text = 'f'
    line = 'second f'
    endidx = len(line)
    begidx = endidx - len(text)
    state = 0

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = sb_app.complete(text, state)

    # It is at end of line, so extra space is present
    assert first_match is not None and sb_app.completion_matches == ['foo ']


def test_cmd2_submenu_completion_single_mid(sb_app):
    text = 'f'
    line = 'second fo'
    endidx = len(line) - 1
    begidx = endidx - len(text)
    state = 0

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = sb_app.complete(text, state)

    assert first_match is not None and sb_app.completion_matches == ['foo']


def test_cmd2_submenu_completion_multiple(sb_app):
    text = ''
    line = 'second '
    endidx = len(line)
    begidx = endidx - len(text)
    state = 0

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = sb_app.complete(text, state)

    assert first_match is not None and sb_app.completion_matches == [
        '_relative_load',
        'alias',
        'edit',
        'eof',
        'eos',
        'foo',
        'help',
        'history',
        'load',
        'py',
        'pyscript',
        'quit',
        'set',
        'shell',
        'shortcuts',
        'unalias'
    ]


def test_cmd2_submenu_completion_nomatch(sb_app):
    text = 'z'
    line = 'second z'
    endidx = len(line)
    begidx = endidx - len(text)
    state = 0

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = sb_app.complete(text, state)

    assert first_match is None


def test_cmd2_submenu_completion_after_submenu_match(sb_app):
    text = 'a'
    line = 'second foo a'
    endidx = len(line)
    begidx = endidx - len(text)
    state = 0

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = sb_app.complete(text, state)

    assert first_match is not None and sb_app.completion_matches == ['asd ']


def test_cmd2_submenu_completion_after_submenu_nomatch(sb_app):
    text = 'b'
    line = 'second foo b'
    endidx = len(line)
    begidx = endidx - len(text)
    state = 0

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = sb_app.complete(text, state)

    assert first_match is None


def test_cmd2_help_submenu_completion_single_mid(sb_app):
    text = 'sec'
    line = 'help seco'
    begidx = len(line) - 4
    endidx = begidx + len(text)
    assert sb_app.complete_help(text, line, begidx, endidx) == ['second']


def test_cmd2_help_submenu_completion_multiple(sb_app):
    text = ''
    line = 'help second '
    endidx = len(line)
    begidx = endidx - len(text)
    assert sb_app.complete_help(text, line, begidx, endidx) == [
        '_relative_load',
        'alias',
        'edit',
        'eof',
        'eos',
        'foo',
        'help',
        'history',
        'load',
        'py',
        'pyscript',
        'quit',
        'set',
        'shell',
        'shortcuts',
        'unalias'
    ]


def test_cmd2_help_submenu_completion_nomatch(sb_app):
    text = 'b'
    line = 'help second b'
    endidx = len(line)
    begidx = endidx - len(text)
    assert sb_app.complete_help(text, line, begidx, endidx) == []


def test_cmd2_help_submenu_completion_subcommands(sb_app):
    text = ''
    line = 'help second '
    endidx = len(line)
    begidx = endidx - len(text)
    assert sb_app.complete_help(text, line, begidx, endidx) == [
        '_relative_load',
        'alias',
        'edit',
        'eof',
        'eos',
        'foo',
        'help',
        'history',
        'load',
        'py',
        'pyscript',
        'quit',
        'set',
        'shell',
        'shortcuts',
        'unalias'
    ]
