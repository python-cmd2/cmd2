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
import readline
import sys

import cmd2
import mock
import pytest

from cmd2 import path_complete, flag_based_complete, index_based_complete

@pytest.fixture
def cmd2_app():
    c = cmd2.Cmd()
    return c

@pytest.fixture
def cs_app():
    c = cmd2.Cmd()
    return c


def test_cmd2_command_completion_single_end(cmd2_app):
    text = 'he'
    line = 'he'
    endidx = len(line)
    begidx = endidx - len(text)
    # It is at end of line, so extra space is present
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help ']

def test_complete_command_single_end(cmd2_app):
    text = 'he'
    line = 'he'
    state = 0
    endidx = len(line)
    begidx = endidx - len(text)

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
                first_match = cmd2_app.complete(text, state)

    assert first_match is not None and cmd2_app.completion_matches == ['help ']

def test_complete_command_invalid_state(cmd2_app):
    text = 'he'
    line = 'he'
    state = 1
    endidx = len(line)
    begidx = endidx - len(text)

    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place get None
                first_match = cmd2_app.complete(text, state)

    assert first_match is None

def test_complete_empty_arg(cmd2_app):
    text = ''
    line = 'help '
    state = 0
    endidx = len(line)
    begidx = endidx - len(text)

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
                first_match = cmd2_app.complete(text, state)

    assert first_match is not None and \
        cmd2_app.completion_matches == cmd2_app.complete_help(text, line, begidx, endidx)

def test_complete_bogus_command(cmd2_app):
    text = ''
    line = 'fizbuzz '
    state = 0
    endidx = len(line)
    begidx = endidx - len(text)

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
                first_match = cmd2_app.complete(text, state)

    assert first_match is None

def test_cmd2_command_completion_is_case_sensitive(cmd2_app):
    text = 'HE'
    line = 'HE'
    endidx = len(line)
    begidx = endidx - len(text)
    # It is at end of line, so extra space is present
    assert cmd2_app.completenames(text, line, begidx, endidx) == []

def test_cmd2_command_completion_single_mid(cmd2_app):
    text = 'he'
    line = 'he'
    begidx = 0
    endidx = 1
    # It is not at end of line, so no extra space
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_cmd2_command_completion_multiple(cmd2_app):
    text = 'h'
    line = 'h'
    endidx = len(line)
    begidx = endidx - len(text)
    # It is not at end of line, so no extra space
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_command_completion_nomatch(cmd2_app):
    text = 'z'
    line = 'z'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == []

def test_cmd2_help_completion_single_end(cmd2_app):
    text = 'he'
    line = 'help he'
    endidx = len(line)
    begidx = endidx - len(text)
    # Even though it is at end of line, no extra space is present when tab completing a command name to get help on
    assert cmd2_app.complete_help(text, line, begidx, endidx) == ['help']

def test_cmd2_help_completion_single_mid(cmd2_app):
    text = 'he'
    line = 'help he'
    begidx = 5
    endidx = 6
    assert cmd2_app.complete_help(text, line, begidx, endidx) == ['help']

def test_cmd2_help_completion_multiple(cmd2_app):
    text = 'h'
    line = 'help h'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_help(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_help_completion_nomatch(cmd2_app):
    text = 'z'
    line = 'help z'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_help(text, line, begidx, endidx) == []

def test_shell_command_completion(cmd2_app):
    if sys.platform == "win32":
        text = 'calc'
        line = 'shell {}'.format(text)
        expected = ['calc.exe ']
    else:
        text = 'egr'
        line = 'shell {}'.format(text)
        expected = ['egrep ']

    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == expected

def test_shell_command_completion_doesnt_match_wildcards(cmd2_app):
    if sys.platform == "win32":
        text = 'c*'
        line = 'shell {}'.format(text)
    else:
        text = 'e*'
        line = 'shell {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_multiple(cmd2_app):
    if sys.platform == "win32":
        text = 'c'
        line = 'shell {}'.format(text)
        expected = 'calc.exe'
    else:
        text = 'l'
        line = 'shell {}'.format(text)
        expected = 'ls'

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
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_does_path_completion_when_after_command(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'shell cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.complete_shell(text, line, begidx, endidx) == ['conftest.py ']


def test_path_completion_single_end(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'shell cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == ['conftest.py ']

def test_path_completion_single_mid(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'tes'
    path = os.path.join(test_dir, 'c')
    line = 'shell cat {}'.format(path)

    begidx = line.find(text)
    endidx = begidx + len(text)

    assert path_complete(text, line, begidx, endidx) == ['tests' + os.path.sep]

def test_path_completion_multiple(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 's'
    path = os.path.join(test_dir, text)
    line = 'shell cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == ['script.py', 'script.txt', 'scripts' + os.path.sep]

def test_path_completion_nomatch(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'z'
    path = os.path.join(test_dir, text)
    line = 'shell cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == []

def test_path_completion_cwd():
    # Run path complete with no path and no search text
    text = ''
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_empty = path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    cwd = os.getcwd()
    line = 'shell ls {}'.format(cwd)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_cwd = path_complete(text, line, begidx, endidx)

    # Verify that the results are the same in both cases and that there is something there
    assert completions_empty == completions_cwd
    assert completions_cwd

def test_path_completion_doesnt_match_wildcards(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c*'
    path = os.path.join(test_dir, text)
    line = 'shell cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    # Currently path completion doesn't accept wildcards, so will always return empty results
    assert path_complete(text, line, begidx, endidx) == []

def test_path_completion_user_expansion():
    # Run path with just a tilde
    text = ''
    if sys.platform.startswith('win'):
        line = 'shell dir ~{}'.format(text)
    else:
        line = 'shell ls ~{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_tilde = path_complete(text, line, begidx, endidx)

    # Run path complete on the user's home directory
    user_dir = os.path.expanduser('~')
    if sys.platform.startswith('win'):
        line = 'shell dir {}'.format(user_dir)
    else:
        line = 'shell ls {}'.format(user_dir)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_home = path_complete(text, line, begidx, endidx)

    # Verify that the results are the same in both cases
    assert completions_tilde == completions_home

def test_path_completion_directories_only(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 's'
    path = os.path.join(test_dir, text)
    line = 'shell cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx, dir_only=True) == ['scripts' + os.path.sep]

def test_path_completion_syntax_err(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'shell cat " {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert path_complete(text, line, begidx, endidx) == []

def test_path_completion_no_tokens():
    text = ''
    line = 'shell'
    endidx = len(line)
    begidx = endidx - len(text)
    assert path_complete(text, line, begidx, endidx) == []


# List of strings used with flag and index based completion functions
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

def test_flag_based_completion_single_end():
    text = 'Pi'
    line = 'list_food -f Pi'
    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == ['Pizza ']

def test_flag_based_completion_single_mid():
    text = 'Pi'
    line = 'list_food -f Pi'
    begidx = len(line) - len(text)
    endidx = begidx + 1

    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == ['Pizza']

def test_flag_based_completion_multiple():
    text = ''
    line = 'list_food -f '
    endidx = len(line)
    begidx = endidx - len(text)
    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == sorted(food_item_strs)

def test_flag_based_completion_nomatch():
    text = 'q'
    line = 'list_food -f q'
    endidx = len(line)
    begidx = endidx - len(text)
    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == []

def test_flag_based_default_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'list_food {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict, path_complete) == ['conftest.py ']

def test_flag_based_callable_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'list_food -o {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict, path_complete) == ['conftest.py ']

def test_flag_based_completion_syntax_err():
    text = 'Pi'
    line = 'list_food -f " Pi'
    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == []

def test_flag_based_completion_no_tokens():
    text = ''
    line = 'list_food'
    endidx = len(line)
    begidx = endidx - len(text)

    assert flag_based_complete(text, line, begidx, endidx, flag_dict) == []


# Dictionary used with index based completion functions
index_dict = \
    {
        1: food_item_strs,   # Tab-complete food items at index 1 in command line
        2: sport_item_strs,  # Tab-complete sport items at index 2 in command line
        3: path_complete,    # Tab-complete using path_complete function at index 3 in command line
    }

def test_index_based_completion_single_end():
    text = 'Foo'
    line = 'command Pizza Foo'
    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict) == ['Football ']

def test_index_based_completion_single_mid():
    text = 'Foo'
    line = 'command Pizza Foo'
    begidx = len(line) - len(text)
    endidx = begidx + 1

    assert index_based_complete(text, line, begidx, endidx, index_dict) == ['Football']

def test_index_based_completion_multiple():
    text = ''
    line = 'command Pizza '
    endidx = len(line)
    begidx = endidx - len(text)
    assert index_based_complete(text, line, begidx, endidx, index_dict) == sorted(sport_item_strs)

def test_index_based_completion_nomatch():
    text = 'q'
    line = 'command q'
    endidx = len(line)
    begidx = endidx - len(text)
    assert index_based_complete(text, line, begidx, endidx, index_dict) == []

def test_index_based_default_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'command Pizza Bat Computer {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict, path_complete) == ['conftest.py ']

def test_index_based_callable_completer(request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = 'command Pizza Bat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict) == ['conftest.py ']

def test_index_based_completion_syntax_err():
    text = 'Foo'
    line = 'command "Pizza Foo'
    endidx = len(line)
    begidx = endidx - len(text)

    assert index_based_complete(text, line, begidx, endidx, index_dict) == []


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

    # Create a list of subcommand names, which is used to enable tab-completion of sub-commands
    subcommands = ['foo', 'bar']

    @cmd2.with_argparser(base_parser, subcommands)
    def do_base(self, args):
        """Base command help"""
        try:
            # Call whatever sub-command function was selected
            args.func(self, args)
        except AttributeError:
            # No sub-command was provided, so as called
            self.do_help('base')


@pytest.fixture
def sc_app():
    app = SubcommandsExample()
    return app


def test_cmd2_subcommand_completion_single_end(sc_app):
    text = 'f'
    line = 'base f'
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
                first_match = sc_app.complete(text, state)

    # It is at end of line, so extra space is present
    assert first_match is not None and sc_app.completion_matches == ['foo ']

def test_cmd2_subcommand_completion_single_mid(sc_app):
    text = 'f'
    line = 'base fo'
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
                first_match = sc_app.complete(text, state)

    assert first_match is not None and sc_app.completion_matches == ['foo']

def test_cmd2_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'base '
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
                first_match = sc_app.complete(text, state)

    assert first_match is not None and sc_app.completion_matches == ['bar', 'foo']

def test_cmd2_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'base z'
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
                first_match = sc_app.complete(text, state)

    assert first_match is None

def test_cmd2_subcommand_completion_after_subcommand(sc_app):
    text = 'f'
    line = 'base foo f'
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
                first_match = sc_app.complete(text, state)

    assert first_match is None

def test_complete_subcommand_single_end(sc_app):
    text = 'f'
    line = 'base f'
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
                first_match = sc_app.complete(text, state)

    assert first_match is not None and sc_app.completion_matches == ['foo ']


def test_cmd2_help_subcommand_completion_single_end(sc_app):
    text = 'base'
    line = 'help base'
    endidx = len(line)
    begidx = endidx - len(text)

    # Commands with subcommands have a space at the end when the cursor is at the end of the line
    assert sc_app.complete_help(text, line, begidx, endidx) == ['base ']

def test_cmd2_help_subcommand_completion_single_mid(sc_app):
    text = 'ba'
    line = 'help base'
    begidx = 5
    endidx = 6
    assert sc_app.complete_help(text, line, begidx, endidx) == ['base']

def test_cmd2_help_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'help base '
    endidx = len(line)
    begidx = endidx - len(text)
    assert sc_app.complete_help(text, line, begidx, endidx) == ['bar', 'foo']

def test_cmd2_help_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'help base z'
    endidx = len(line)
    begidx = endidx - len(text)
    assert sc_app.complete_help(text, line, begidx, endidx) == []
