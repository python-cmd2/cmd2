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
        self.called_postparsing = 0
        self.called_precmd = 0

    def prepost_hook_one(self):
        "Method used for preloop or postloop hooks"
        self.poutput("one")

    def prepost_hook_two(self):
        "Another method used for preloop or postloop hooks"
        self.poutput("two")

    def postparse_hook(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        "A postparsing hook"
        self.called_postparsing += 1
        return False, statement

    def postparse_hook_stop(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        "A postparsing hook with requests application exit"
        self.called_postparsing += 1
        return True, statement

    def postparse_hook_emptystatement(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        "A postparsing hook with raises an EmptyStatement exception"
        self.called_postparsing += 1
        raise cmd2.EmptyStatement

    def postparse_hook_exception(self, statement: cmd2.Statement) -> Tuple[bool, cmd2.Statement]:
        "A postparsing hook which raises an exception"
        self.called_postparsing += 1
        raise ValueError

    def precmd(self, statement: cmd2.Statement) -> cmd2.Statement:
        "Override cmd.Cmd method"
        self.called_precmd += 1
        return statement

    def precmd_hook(self, statement: cmd2.Statement) -> cmd2.Statement:
        "A precommand hook"
        self.called_precmd += 1
        return statement

    def precmd_hook_emptystatement(self, statement: cmd2.Statement) -> cmd2.Statement:
        "A precommand hook which raises an EmptyStatement exception"
        self.called_precmd += 1
        raise cmd2.EmptyStatement

    def precmd_hook_exception(self, statement: cmd2.Statement) -> cmd2.Statement:
        "A precommand hook which raises an exception"
        self.called_precmd += 1
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
# test pre and postloop hooks
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

###
#
# test postparsing hooks
#
###
def test_postparsing_hook(capsys):
    app = PluggedApp()
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert not app.called_postparsing

    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_postparsing == 1

    # register the function again, so it should be called twice
    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_postparsing == 2

def test_postparsing_hook_stop_first(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.postparse_hook_stop)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_postparsing == 1
    assert stop

    # register another function but it shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_postparsing == 1
    assert stop

def test_postparsing_hook_stop_second(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.postparse_hook)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_postparsing == 1
    assert not stop

    # register another function and make sure it gets called
    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook_stop)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_postparsing == 2
    assert stop

    # register a third function which shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook)
    stop = app.onecmd_plus_hooks('say hello')
    assert app.called_postparsing == 2
    assert stop

def test_postparsing_hook_emptystatement_first(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.postparse_hook_emptystatement)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    assert app.called_postparsing == 1

    # register another function but it shouldn't be called
    app.reset_counters()
    stop = app.register_postparsing_hook(app.postparse_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    assert app.called_postparsing == 1

def test_postparsing_hook_emptystatement_second(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.postparse_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert not err
    assert app.called_postparsing == 1

    # register another function and make sure it gets called
    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook_emptystatement)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    assert app.called_postparsing == 2

    # register a third function which shouldn't be called
    app.reset_counters()
    app.register_postparsing_hook(app.postparse_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    assert app.called_postparsing == 2

def test_postparsing_hook_exception(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.postparse_hook_exception)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert err
    assert app.called_postparsing == 1

    # register another function, but it shouldn't be called
    app.reset_counters()
    stop = app.register_postparsing_hook(app.postparse_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert err
    assert app.called_postparsing == 1

###
#
# test precmd hooks
#
#####
def test_precmd_hook(capsys):
    app = PluggedApp()
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    # without registering any hooks, precmd() should be called
    assert app.called_precmd == 1

    app.reset_counters()
    app.register_precmd_hook(app.precmd_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    # with one hook registered, we should get precmd() and the hook
    assert app.called_precmd == 2

    # register the function again, so it should be called twice
    app.reset_counters()
    app.register_precmd_hook(app.precmd_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    # with two hooks registered, we should get precmd() and both hooks
    assert app.called_precmd == 3

def test_precmd_hook_emptystatement_first(capsys):
    app = PluggedApp()
    app.register_precmd_hook(app.precmd_hook_emptystatement)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    # since the registered hooks are called before precmd(), if a registered
    # hook throws an exception, precmd() is never called
    assert app.called_precmd == 1

    # register another function but it shouldn't be called
    app.reset_counters()
    stop = app.register_precmd_hook(app.precmd_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    # the exception raised by the first hook should prevent the second
    # hook from being called, and it also prevents precmd() from being
    # called
    assert app.called_precmd == 1

def test_precmd_hook_emptystatement_second(capsys):
    app = PluggedApp()
    app.register_precmd_hook(app.precmd_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert not err
    # with one hook registered, we should get precmd() and the hook
    assert app.called_precmd == 2

    # register another function and make sure it gets called
    app.reset_counters()
    app.register_precmd_hook(app.precmd_hook_emptystatement)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    # since the registered hooks are called before precmd(), if a registered
    # hook throws an exception, precmd() is never called
    assert app.called_precmd == 2

    # register a third function which shouldn't be called
    app.reset_counters()
    app.register_precmd_hook(app.precmd_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert not out
    assert not err
    # the exception raised by the second hook should prevent the third
    # hook from being called. since the registered hooks are called before precmd(),
    # if a registered hook throws an exception, precmd() is never called
    assert app.called_precmd == 2

###
#
# test postcmd hooks
#
####
def test_postcmd(capsys):
    pass

##
#
# command finalization
#
###
def test_cmdfinalization(capsys):
    pass

