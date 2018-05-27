# coding=utf-8
"""
Test plugin infrastructure and hooks.

Copyright 2018 Jared Crapo <jared@kotfu.net>
Released under MIT license, see LICENSE file
"""

from typing import Tuple

import pytest

import cmd2

from .conftest import StdOut

class Plugin:
    "A mixin class for testing hook registration and calling"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_counters()

    def reset_counters(self):
        self.called_pph = 0

    def prepost_hook_one(self):
        self.poutput("one")

    def prepost_hook_two(self):
        self.poutput("two")

    def pph(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        self.called_pph += 1
        return False, statement

    def pph_stop(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        self.called_pph += 1
        return True, statement

    def pph_emptystatement(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        self.called_pph += 1
        raise cmd2.EmptyStatement

    def pph_exception(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        self.called_pph += 1
        raise ValueError

class PluggedApp(Plugin, cmd2.Cmd):
    "A sample app with a plugin mixed in"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_say(self, statement):
        """Repeat back the arguments"""
        self.poutput(statement)

###
#
# test hooks
#
###
def test_preloop_hook(capsys):
    app = PluggedApp()
    app.register_preloop_hook(app.prepost_hook_one)
    app.cmdqueue.append('say hello')
    app.cmdqueue.append('quit')
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'one\nhello\n'
    assert not err

def test_preloop_hooks(capsys):
    app = PluggedApp()
    app.register_preloop_hook(app.prepost_hook_one)
    app.register_preloop_hook(app.prepost_hook_two)
    app.cmdqueue.append('say hello')
    app.cmdqueue.append('quit')
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'one\ntwo\nhello\n'
    assert not err

def test_postloop_hook(capsys):
    app = PluggedApp()
    app.register_postloop_hook(app.prepost_hook_one)
    app.cmdqueue.append('say hello')
    app.cmdqueue.append('quit')
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'hello\none\n'
    assert not err

def test_postloop_hooks(capsys):
    app = PluggedApp()
    app.register_postloop_hook(app.prepost_hook_one)
    app.register_postloop_hook(app.prepost_hook_two)
    app.cmdqueue.append('say hello')
    app.cmdqueue.append('quit')
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'hello\none\ntwo\n'
    assert not err

def test_postparsing_hook(capsys):
    app = PluggedApp()
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert not app.called_pph

    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_pph == 1

    # register the function again, so it should be called
    # twice
    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_pph == 2

def test_postparsing_hook_stop_first(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.pph_stop)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_pph == 1
    assert stop

    # register another function but it shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_pph == 1
    assert stop

def test_postparsing_hook_stop_second(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.pph)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_pph == 1
    assert not stop

    # register another function and make sure it gets called
    app.reset_counters()
    app.register_postparsing_hook(app.pph_stop)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_pph == 2
    assert stop

    # register a third function which shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_pph == 2
    assert stop

def test_postparsing_hook_emptystatement_first(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.pph_emptystatement)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not out
    assert not err
    assert app.called_pph == 1

    # register another function but it shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not out
    assert not err
    assert app.called_pph == 1

def test_postparsing_hook_emptystatement_second(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.pph)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_pph == 1

    # register another function and make sure it gets called
    app.reset_counters()
    app.register_postparsing_hook(app.pph_emptystatement)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not out
    assert not err
    assert app.called_pph == 2

    # register a third function which shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not out
    assert not err
    assert app.called_pph == 2
    assert not stop

def test_postparsing_hook_exception(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.pph_exception)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not out
    assert err
    assert app.called_pph == 1

    # register another function, but it shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.pph)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not out
    assert err
    assert app.called_pph == 1
