# coding=utf-8
"""
Unit/functional testing for readline tab-completion functions in the cmd2.py module.

These are primarily tests related to readline completer functions which handle tab-completion of cmd2/cmd commands,
file system paths, and shell commands.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import sys

import cmd2
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
