# coding=utf-8
"""
Unit/functional testing for readline tab-completion functions in the cmd2.py module.

These are primarily tests related to readline completer functions which handle tab-completion of cmd2/cmd commands,
file system paths, and shell commands.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
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

# TODO: Add tests for path completion
