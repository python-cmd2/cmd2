# coding=utf-8
# flake8: noqa E302
"""
Test plugin infrastructure and hooks.
"""
import argparse
import sys

import pytest

import cmd2
from cmd2 import Cmd2ArgumentParser, exceptions, plugin, with_argparser

# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock



class Plugin:
    """A mixin class for testing hook registration and calling"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_counters()

    def reset_counters(self):
        self.called_preparse = 0
        self.called_postparsing = 0
        self.called_precmd = 0
        self.called_postcmd = 0
        self.called_cmdfinalization = 0

    ###
    #
    # preloop and postloop hooks
    # which share the same signature and are thus interchangable
    #
    ###
    def prepost_hook_one(self) -> None:
        """Method used for preloop or postloop hooks"""
        self.poutput("one")

    def prepost_hook_two(self) -> None:
        """Another method used for preloop or postloop hooks"""
        self.poutput("two")

    def prepost_hook_too_many_parameters(self, param) -> None:
        """A preloop or postloop hook with too many parameters"""
        pass

    def prepost_hook_with_wrong_return_annotation(self) -> bool:
        """A preloop or postloop hook with incorrect return type"""
        pass

    ###
    #
    # preparse hook
    #
    ###
    def preparse(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Preparsing hook"""
        self.called_preparse += 1
        return data

    ###
    #
    # Postparsing hooks
    #
    ###
    def postparse_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A postparsing hook"""
        self.called_postparsing += 1
        return data

    def postparse_hook_stop(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A postparsing hook with requests application exit"""
        self.called_postparsing += 1
        data.stop = True
        return data

    def postparse_hook_emptystatement(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A postparsing hook with raises an EmptyStatement exception"""
        self.called_postparsing += 1
        raise exceptions.EmptyStatement

    def postparse_hook_exception(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """A postparsing hook which raises an exception"""
        self.called_postparsing += 1
        raise ValueError

    def postparse_hook_too_many_parameters(self, data1, data2) -> cmd2.plugin.PostparsingData:
        """A postparsing hook with too many parameters"""
        pass

    def postparse_hook_undeclared_parameter_annotation(self, data) -> cmd2.plugin.PostparsingData:
        """A postparsing hook with an undeclared parameter type"""
        pass

    def postparse_hook_wrong_parameter_annotation(self, data: str) -> cmd2.plugin.PostparsingData:
        """A postparsing hook with the wrong parameter type"""
        pass

    def postparse_hook_undeclared_return_annotation(self, data: cmd2.plugin.PostparsingData):
        """A postparsing hook with an undeclared return type"""
        pass

    def postparse_hook_wrong_return_annotation(self, data: cmd2.plugin.PostparsingData) -> str:
        """A postparsing hook with the wrong return type"""
        pass

    ###
    #
    # precommand hooks, some valid, some invalid
    #
    ###
    def precmd(self, statement: cmd2.Statement) -> cmd2.Statement:
        """Override cmd.Cmd method"""
        self.called_precmd += 1
        return statement

    def precmd_hook(self, data: plugin.PrecommandData) -> plugin.PrecommandData:
        """A precommand hook"""
        self.called_precmd += 1
        return data

    def precmd_hook_emptystatement(self, data: plugin.PrecommandData) -> plugin.PrecommandData:
        """A precommand hook which raises an EmptyStatement exception"""
        self.called_precmd += 1
        raise exceptions.EmptyStatement

    def precmd_hook_exception(self, data: plugin.PrecommandData) -> plugin.PrecommandData:
        """A precommand hook which raises an exception"""
        self.called_precmd += 1
        raise ValueError

    def precmd_hook_not_enough_parameters(self) -> plugin.PrecommandData:
        """A precommand hook with no parameters"""
        pass

    def precmd_hook_too_many_parameters(self, one: plugin.PrecommandData, two: str) -> plugin.PrecommandData:
        """A precommand hook with too many parameters"""
        return one

    def precmd_hook_no_parameter_annotation(self, data) -> plugin.PrecommandData:
        """A precommand hook with no type annotation on the parameter"""
        return data

    def precmd_hook_wrong_parameter_annotation(self, data: str) -> plugin.PrecommandData:
        """A precommand hook with the incorrect type annotation on the parameter"""
        return data

    def precmd_hook_no_return_annotation(self, data: plugin.PrecommandData):
        """A precommand hook with no type annotation on the return value"""
        return data

    def precmd_hook_wrong_return_annotation(self, data: plugin.PrecommandData) -> cmd2.Statement:
        return self.statement_parser.parse('hi there')

    ###
    #
    # postcommand hooks, some valid, some invalid
    #
    ###
    def postcmd(self, stop: bool, statement: cmd2.Statement) -> bool:
        """Override cmd.Cmd method"""
        self.called_postcmd += 1
        return stop

    def postcmd_hook(self, data: plugin.PostcommandData) -> plugin.PostcommandData:
        """A postcommand hook"""
        self.called_postcmd += 1
        return data

    def postcmd_hook_exception(self, data: plugin.PostcommandData) -> plugin.PostcommandData:
        """A postcommand hook with raises an exception"""
        self.called_postcmd += 1
        raise ZeroDivisionError

    def postcmd_hook_not_enough_parameters(self) -> plugin.PostcommandData:
        """A precommand hook with no parameters"""
        pass

    def postcmd_hook_too_many_parameters(self, one: plugin.PostcommandData, two: str) -> plugin.PostcommandData:
        """A precommand hook with too many parameters"""
        return one

    def postcmd_hook_no_parameter_annotation(self, data) -> plugin.PostcommandData:
        """A precommand hook with no type annotation on the parameter"""
        return data

    def postcmd_hook_wrong_parameter_annotation(self, data: str) -> plugin.PostcommandData:
        """A precommand hook with the incorrect type annotation on the parameter"""
        return data

    def postcmd_hook_no_return_annotation(self, data: plugin.PostcommandData):
        """A precommand hook with no type annotation on the return value"""
        return data

    def postcmd_hook_wrong_return_annotation(self, data: plugin.PostcommandData) -> cmd2.Statement:
        return self.statement_parser.parse('hi there')

    ###
    #
    # command finalization hooks, some valid, some invalid
    #
    ###
    def cmdfinalization_hook(self, data: plugin.CommandFinalizationData) -> plugin.CommandFinalizationData:
        """A command finalization hook."""
        self.called_cmdfinalization += 1
        return data

    def cmdfinalization_hook_stop(self, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
        """A command finalization hook which requests application exit"""
        self.called_cmdfinalization += 1
        data.stop = True
        return data

    def cmdfinalization_hook_exception(self, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
        """A command finalization hook which raises an exception"""
        self.called_cmdfinalization += 1
        raise ValueError

    def cmdfinalization_hook_system_exit(self, data: cmd2.plugin.CommandFinalizationData) -> \
            cmd2.plugin.CommandFinalizationData:
        """A command finalization hook which raises a SystemExit"""
        self.called_cmdfinalization += 1
        raise SystemExit

    def cmdfinalization_hook_keyboard_interrupt(self, data: cmd2.plugin.CommandFinalizationData) -> \
            cmd2.plugin.CommandFinalizationData:
        """A command finalization hook which raises a KeyboardInterrupt"""
        self.called_cmdfinalization += 1
        raise KeyboardInterrupt

    def cmdfinalization_hook_not_enough_parameters(self) -> plugin.CommandFinalizationData:
        """A command finalization hook with no parameters."""
        pass

    def cmdfinalization_hook_too_many_parameters(self, one: plugin.CommandFinalizationData, two: str) -> \
            plugin.CommandFinalizationData:
        """A command finalization hook with too many parameters."""
        return one

    def cmdfinalization_hook_no_parameter_annotation(self, data) -> plugin.CommandFinalizationData:
        """A command finalization hook with no type annotation on the parameter."""
        return data

    def cmdfinalization_hook_wrong_parameter_annotation(self, data: str) -> plugin.CommandFinalizationData:
        """A command finalization hook with the incorrect type annotation on the parameter."""
        return data

    def cmdfinalization_hook_no_return_annotation(self, data: plugin.CommandFinalizationData):
        """A command finalizationhook with no type annotation on the return value."""
        return data

    def cmdfinalization_hook_wrong_return_annotation(self, data: plugin.CommandFinalizationData) -> cmd2.Statement:
        """A command finalization hook with the wrong return type annotation."""
        return self.statement_parser.parse('hi there')


class PluggedApp(Plugin, cmd2.Cmd):
    """A sample app with a plugin mixed in"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_say(self, statement):
        """Repeat back the arguments"""
        self.poutput(statement)

    def do_skip_postcmd_hooks(self, _):
        self.poutput("In do_skip_postcmd_hooks")
        raise exceptions.SkipPostcommandHooks

    parser = Cmd2ArgumentParser(description="Test parser")
    parser.add_argument("my_arg", help="some help text")

    @with_argparser(parser)
    def do_argparse_cmd(self, namespace: argparse.Namespace):
        """Repeat back the arguments"""
        self.poutput(namespace.__statement__)

###
#
# test pre and postloop hooks
#
###
def test_register_preloop_hook_too_many_parameters():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_preloop_hook(app.prepost_hook_too_many_parameters)

def test_register_preloop_hook_with_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_preloop_hook(app.prepost_hook_with_wrong_return_annotation)

def test_preloop_hook(capsys):
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog", "say hello", 'quit']

    with mock.patch.object(sys, 'argv', testargs):
        app = PluggedApp()

    app.register_preloop_hook(app.prepost_hook_one)
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'one\nhello\n'
    assert not err

def test_preloop_hooks(capsys):
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog", "say hello", 'quit']

    with mock.patch.object(sys, 'argv', testargs):
        app = PluggedApp()

    app.register_preloop_hook(app.prepost_hook_one)
    app.register_preloop_hook(app.prepost_hook_two)
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'one\ntwo\nhello\n'
    assert not err

def test_register_postloop_hook_too_many_parameters():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postloop_hook(app.prepost_hook_too_many_parameters)

def test_register_postloop_hook_with_wrong_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postloop_hook(app.prepost_hook_with_wrong_return_annotation)

def test_postloop_hook(capsys):
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog", "say hello", 'quit']

    with mock.patch.object(sys, 'argv', testargs):
        app = PluggedApp()

    app.register_postloop_hook(app.prepost_hook_one)
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'hello\none\n'
    assert not err

def test_postloop_hooks(capsys):
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog", "say hello", 'quit']

    with mock.patch.object(sys, 'argv', testargs):
        app = PluggedApp()

    app.register_postloop_hook(app.prepost_hook_one)
    app.register_postloop_hook(app.prepost_hook_two)
    app.cmdloop()
    out, err = capsys.readouterr()
    assert out == 'hello\none\ntwo\n'
    assert not err

###
#
# test preparse hook
#
###
def test_preparse(capsys):
    app = PluggedApp()
    app.register_postparsing_hook(app.preparse)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_preparse == 1

###
#
# test postparsing hooks
#
###
def test_postparsing_hook_too_many_parameters():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postparsing_hook(app.postparse_hook_too_many_parameters)

def test_postparsing_hook_undeclared_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postparsing_hook(app.postparse_hook_undeclared_parameter_annotation)

def test_postparsing_hook_wrong_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postparsing_hook(app.postparse_hook_wrong_parameter_annotation)

def test_postparsing_hook_undeclared_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postparsing_hook(app.postparse_hook_undeclared_return_annotation)

def test_postparsing_hook_wrong_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postparsing_hook(app.postparse_hook_wrong_return_annotation)

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
    app.register_postparsing_hook(app.postparse_hook)
    stop = app.onecmd_plus_hooks('say hello')
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
def test_register_precmd_hook_parameter_count():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_precmd_hook(app.precmd_hook_not_enough_parameters)
    with pytest.raises(TypeError):
        app.register_precmd_hook(app.precmd_hook_too_many_parameters)

def test_register_precmd_hook_no_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_precmd_hook(app.precmd_hook_no_parameter_annotation)

def test_register_precmd_hook_wrong_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_precmd_hook(app.precmd_hook_wrong_parameter_annotation)

def test_register_precmd_hook_no_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_precmd_hook(app.precmd_hook_no_return_annotation)

def test_register_precmd_hook_wrong_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_precmd_hook(app.precmd_hook_wrong_return_annotation)

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
def test_register_postcmd_hook_parameter_count():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postcmd_hook(app.postcmd_hook_not_enough_parameters)
    with pytest.raises(TypeError):
        app.register_postcmd_hook(app.postcmd_hook_too_many_parameters)

def test_register_postcmd_hook_no_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postcmd_hook(app.postcmd_hook_no_parameter_annotation)

def test_register_postcmd_hook_wrong_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postcmd_hook(app.postcmd_hook_wrong_parameter_annotation)

def test_register_postcmd_hook_no_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postcmd_hook(app.postcmd_hook_no_return_annotation)

def test_register_postcmd_hook_wrong_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_postcmd_hook(app.postcmd_hook_wrong_return_annotation)

def test_postcmd(capsys):
    app = PluggedApp()
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    # without registering any hooks, postcmd() should be called
    assert app.called_postcmd == 1

    app.reset_counters()
    app.register_postcmd_hook(app.postcmd_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    # with one hook registered, we should get precmd() and the hook
    assert app.called_postcmd == 2

    # register the function again, so it should be called twice
    app.reset_counters()
    app.register_postcmd_hook(app.postcmd_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    # with two hooks registered, we should get precmd() and both hooks
    assert app.called_postcmd == 3

def test_postcmd_exception_first(capsys):
    app = PluggedApp()
    app.register_postcmd_hook(app.postcmd_hook_exception)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert err
    # since the registered hooks are called before postcmd(), if a registered
    # hook throws an exception, postcmd() is never called. So we should have
    # a count of one because we called the hook that raised the exception
    assert app.called_postcmd == 1

    # register another function but it shouldn't be called
    app.reset_counters()
    stop = app.register_postcmd_hook(app.postcmd_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert err
    # the exception raised by the first hook should prevent the second
    # hook from being called, and it also prevents postcmd() from being
    # called
    assert app.called_postcmd == 1

def test_postcmd_exception_second(capsys):
    app = PluggedApp()
    app.register_postcmd_hook(app.postcmd_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert not err
    # with one hook registered, we should get the hook and postcmd()
    assert app.called_postcmd == 2

    # register another function which should be called
    app.reset_counters()
    stop = app.register_postcmd_hook(app.postcmd_hook_exception)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert err
    # the exception raised by the first hook should prevent the second
    # hook from being called, and it also prevents postcmd() from being
    # called. So we have the first hook, and the second hook, which raised
    # the exception
    assert app.called_postcmd == 2

##
#
# command finalization
#
###
def test_register_cmdfinalization_hook_parameter_count():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_cmdfinalization_hook(app.cmdfinalization_hook_not_enough_parameters)
    with pytest.raises(TypeError):
        app.register_cmdfinalization_hook(app.cmdfinalization_hook_too_many_parameters)

def test_register_cmdfinalization_hook_no_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_cmdfinalization_hook(app.cmdfinalization_hook_no_parameter_annotation)

def test_register_cmdfinalization_hook_wrong_parameter_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_cmdfinalization_hook(app.cmdfinalization_hook_wrong_parameter_annotation)

def test_register_cmdfinalization_hook_no_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_cmdfinalization_hook(app.cmdfinalization_hook_no_return_annotation)

def test_register_cmdfinalization_hook_wrong_return_annotation():
    app = PluggedApp()
    with pytest.raises(TypeError):
        app.register_cmdfinalization_hook(app.cmdfinalization_hook_wrong_return_annotation)

def test_cmdfinalization(capsys):
    app = PluggedApp()
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_cmdfinalization == 0

    app.register_cmdfinalization_hook(app.cmdfinalization_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_cmdfinalization == 1

    # register the function again, so it should be called twice
    app.reset_counters()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook)
    app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_cmdfinalization == 2

def test_cmdfinalization_stop_first(capsys):
    app = PluggedApp()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook_stop)
    app.register_cmdfinalization_hook(app.cmdfinalization_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_cmdfinalization == 2
    assert stop

def test_cmdfinalization_stop_second(capsys):
    app = PluggedApp()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook)
    app.register_cmdfinalization_hook(app.cmdfinalization_hook_stop)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert out == 'hello\n'
    assert not err
    assert app.called_cmdfinalization == 2
    assert stop

def test_cmdfinalization_hook_exception(capsys):
    app = PluggedApp()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook_exception)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert err
    assert app.called_cmdfinalization == 1

    # register another function, but it shouldn't be called
    app.reset_counters()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook)
    stop = app.onecmd_plus_hooks('say hello')
    out, err = capsys.readouterr()
    assert not stop
    assert out == 'hello\n'
    assert err
    assert app.called_cmdfinalization == 1

def test_cmdfinalization_hook_system_exit(capsys):
    app = PluggedApp()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook_system_exit)
    stop = app.onecmd_plus_hooks('say hello')
    assert stop
    assert app.called_cmdfinalization == 1

def test_cmdfinalization_hook_keyboard_interrupt(capsys):
    app = PluggedApp()
    app.register_cmdfinalization_hook(app.cmdfinalization_hook_keyboard_interrupt)

    # First make sure KeyboardInterrupt isn't raised unless told to
    stop = app.onecmd_plus_hooks('say hello', raise_keyboard_interrupt=False)
    assert not stop
    assert app.called_cmdfinalization == 1

    # Now enable raising the KeyboardInterrupt
    app.reset_counters()
    with pytest.raises(KeyboardInterrupt):
        stop = app.onecmd_plus_hooks('say hello', raise_keyboard_interrupt=True)
    assert not stop
    assert app.called_cmdfinalization == 1

    # Now make sure KeyboardInterrupt isn't raised if stop is already True
    app.reset_counters()
    stop = app.onecmd_plus_hooks('quit', raise_keyboard_interrupt=True)
    assert stop
    assert app.called_cmdfinalization == 1

def test_skip_postcmd_hooks(capsys):
    app = PluggedApp()
    app.register_postcmd_hook(app.postcmd_hook)
    app.register_cmdfinalization_hook(app.cmdfinalization_hook)

    # Cause a SkipPostcommandHooks exception and verify no postcmd stuff runs but cmdfinalization_hook still does
    app.onecmd_plus_hooks('skip_postcmd_hooks')
    out, err = capsys.readouterr()
    assert "In do_skip_postcmd_hooks" in out
    assert app.called_postcmd == 0
    assert app.called_cmdfinalization == 1

def test_cmd2_argparse_exception(capsys):
    """
    Verify Cmd2ArgparseErrors raised after calling a command prevent postcmd events from
    running but do not affect cmdfinalization events
    """
    app = PluggedApp()
    app.register_postcmd_hook(app.postcmd_hook)
    app.register_cmdfinalization_hook(app.cmdfinalization_hook)

    # First generate no exception and make sure postcmd_hook, postcmd, and cmdfinalization_hook run
    app.onecmd_plus_hooks('argparse_cmd arg_val')
    out, err = capsys.readouterr()
    assert out == 'arg_val\n'
    assert not err
    assert app.called_postcmd == 2
    assert app.called_cmdfinalization == 1

    app.reset_counters()

    # Next cause an argparse exception and verify no postcmd stuff runs but cmdfinalization_hook still does
    app.onecmd_plus_hooks('argparse_cmd')
    out, err = capsys.readouterr()
    assert not out
    assert "Error: the following arguments are required: my_arg" in err
    assert app.called_postcmd == 0
    assert app.called_cmdfinalization == 1
