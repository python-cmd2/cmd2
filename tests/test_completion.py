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


@pytest.fixture
def cmd2_app():
    c = cmd2.Cmd()
    return c

@pytest.fixture
def cs_app():
    cmd2.Cmd.case_insensitive = False
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
                completion = cmd2_app.complete(text, state)
    assert completion == 'help '

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
                completion = cmd2_app.complete(text, state)
    assert completion is None

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
                completion = cmd2_app.complete(text, state)

    assert completion == cmd2_app.complete_help(text, line, begidx, endidx)[0]

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
                completion = cmd2_app.complete(text, state)

    assert completion is None

def test_cmd2_command_completion_is_case_insensitive_by_default(cmd2_app):
    text = 'HE'
    line = 'HE'
    endidx = len(line)
    begidx = endidx - len(text)
    # It is at end of line, so extra space is present
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help ']

def test_cmd2_case_sensitive_command_completion(cs_app):
    text = 'HE'
    line = 'HE'
    endidx = len(line)
    begidx = endidx - len(text)
    # It is at end of line, so extra space is present
    assert cs_app.completenames(text, line, begidx, endidx) == []

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
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_cmd2_help_completion_single_mid(cmd2_app):
    text = 'he'
    line = 'help he'
    begidx = 5
    endidx = 6
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_cmd2_help_completion_multiple(cmd2_app):
    text = 'h'
    line = 'help h'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_help_completion_nomatch(cmd2_app):
    text = 'z'
    line = 'help z'
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == []

def test_shell_command_completion(cmd2_app):
    if sys.platform == "win32":
        text = 'calc'
        line = 'shell {}'.format(text)
        expected = ['calc.exe ']
    else:
        text = 'egr'
        line = '!{}'.format(text)
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
        line = '!{}'.format(text)

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
        line = '!{}'.format(text)
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
    if sys.platform == "win32":
        line = 'shell'.format(text)
    else:
        line = '!'.format(text)

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


def test_path_completion_single_end(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c'
    path = os.path.join(test_dir, text)
    line = '!cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == ['conftest.py ']

def test_path_completion_single_mid(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'tes'
    path = os.path.join(test_dir, 'c')
    line = '!cat {}'.format(path)

    begidx = line.find(text)
    endidx = begidx + len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == ['tests' + os.path.sep]

def test_path_completion_multiple(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 's'
    path = os.path.join(test_dir, text)
    line = '!cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == ['script.py', 'script.txt', 'scripts' + os.path.sep]

def test_path_completion_nomatch(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'z'
    path = os.path.join(test_dir, text)
    line = '!cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == []

def test_path_completion_cwd(cmd2_app):
    # Run path complete with no path and no search text
    text = ''
    line = '!ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_empty = cmd2_app.path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    cwd = os.getcwd()
    line = '!ls {}'.format(cwd)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_cwd = cmd2_app.path_complete(text, line, begidx, endidx)

    # Verify that the results are the same in both cases and that there is something there
    assert completions_empty == completions_cwd
    assert completions_cwd

def test_path_completion_doesnt_match_wildcards(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'c*'
    path = os.path.join(test_dir, text)
    line = '!cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    # Currently path completion doesn't accept wildcards, so will always return empty results
    assert cmd2_app.path_complete(text, line, begidx, endidx) == []

def test_path_completion_user_expansion(cmd2_app):
    # Run path with just a tilde
    text = ''
    if sys.platform.startswith('win'):
        line = '!dir ~\{}'.format(text)
    else:
        line = '!ls ~/{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_tilde = cmd2_app.path_complete(text, line, begidx, endidx)

    # Run path complete on the user's home directory
    user_dir = os.path.expanduser('~')
    if sys.platform.startswith('win'):
        line = '!dir {}'.format(user_dir)
    else:
        line = '!ls {}'.format(user_dir)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_home = cmd2_app.path_complete(text, line, begidx, endidx)

    # Verify that the results are the same in both cases
    assert completions_tilde == completions_home

    # This next assert fails on AppVeyor Windows containers, but works fine on my Windows 10 VM
    if not sys.platform.startswith('win'):
        # Verify that there is something there
        assert completions_tilde

def test_path_completion_directories_only(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 's'
    path = os.path.join(test_dir, text)
    line = '!cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx, dir_only=True) == ['scripts' + os.path.sep]


def test_parseline_command_and_args(cmd2_app):
    line = 'help history'
    command, args, out_line = cmd2_app.parseline(line)
    assert command == 'help'
    assert args == 'history'
    assert line == out_line

def test_parseline_emptyline(cmd2_app):
    line = ''
    command, args, out_line = cmd2_app.parseline(line)
    assert command == None
    assert args == None
    assert line == out_line

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
        """bar sucommand of base command"""
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

    # It is at end of line, so extra space is present
    assert sc_app.complete_subcommand(text, line, begidx, endidx) == ['foo ']

def test_cmd2_subcommand_completion_single_mid(sc_app):
    text = 'f'
    line = 'base f'
    endidx = len(line) - 1
    begidx = endidx - len(text)

    # It is at end of line, so extra space is present
    assert sc_app.complete_subcommand(text, line, begidx, endidx) == ['foo']

def test_cmd2_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'base '
    endidx = len(line)
    begidx = endidx - len(text)

    # It is at end of line, so extra space is present
    assert sc_app.complete_subcommand(text, line, begidx, endidx) == ['foo', 'bar']

def test_cmd2_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'base z'
    endidx = len(line)
    begidx = endidx - len(text)

    # It is at end of line, so extra space is present
    assert sc_app.complete_subcommand(text, line, begidx, endidx) == []

def test_cmd2_subcommand_completion_after_subcommand(sc_app):
    text = 'f'
    line = 'base foo f'
    endidx = len(line)
    begidx = endidx - len(text)

    # It is at end of line, so extra space is present
    assert sc_app.complete_subcommand(text, line, begidx, endidx) == []


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
                completion = sc_app.complete(text, state)
    assert completion == 'foo '
