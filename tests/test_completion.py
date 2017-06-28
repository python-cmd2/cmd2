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


def test_cmd2_command_completion_single_end(cmd2_app):
    text = 'he'
    line = 'he'
    begidx = 0
    endidx = 2
    # It is at end of line, so extra space is present
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help ']

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
    begidx = 0
    endidx = 1
    # It is not at end of line, so no extra space
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_command_completion_nomatch(cmd2_app):
    text = 'z'
    line = 'z'
    begidx = 0
    endidx = 1
    assert cmd2_app.completenames(text, line, begidx, endidx) == []

def test_cmd2_help_completion_single_end(cmd2_app):
    text = 'he'
    line = 'help he'
    begidx = 5
    endidx = 7
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
    begidx = 5
    endidx = 6
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_help_completion_nomatch(cmd2_app):
    text = 'z'
    line = 'help z'
    begidx = 5
    endidx = 6
    assert cmd2_app.completenames(text, line, begidx, endidx) == []

def test_shell_command_completion(cmd2_app):
    if sys.platform == "win32":
        text = 'calc'
        line = 'shell calc'
        begidx = 6
        endidx = 10
        assert cmd2_app.complete_shell(text, line, begidx, endidx) == ['calc.exe ']
    else:
        text = 'eg'
        line = '!eg'
        begidx = 1
        endidx = 3
        assert cmd2_app.complete_shell(text, line, begidx, endidx) == ['egrep ']

def test_shell_command_completion_multiple(cmd2_app):
    if sys.platform == "win32":
        text = 'c'
        line = 'shell c'
        begidx = 6
        endidx = 7
        assert 'calc.exe' in cmd2_app.complete_shell(text, line, begidx, endidx)
    else:
        text = 'l'
        line = '!l'
        begidx = 1
        endidx = 2
        assert 'ls' in cmd2_app.complete_shell(text, line, begidx, endidx)

def test_shell_command_completion_nomatch(cmd2_app):
    text = 'zzzz'
    line = 'shell zzzz'
    begidx = 6
    endidx = 10
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

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

    assert cmd2_app.path_complete(text, line, begidx, endidx) == ['script.py', 'script.txt', 'scripts/']

def test_path_completion_nomatch(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = 'z'
    path = os.path.join(test_dir, text)
    line = '!cat {}'.format(path)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == []

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
