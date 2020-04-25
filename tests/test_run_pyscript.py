# coding=utf-8
# flake8: noqa E302
"""
Unit/functional testing for run_pytest in cmd2
"""
import builtins
import os

import pytest

from cmd2 import plugin, utils

from .conftest import odd_file_names, run_cmd

# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock

HOOK_OUTPUT = "TEST_OUTPUT"

def cmdfinalization_hook(data: plugin.CommandFinalizationData) -> plugin.CommandFinalizationData:
    """A cmdfinalization_hook hook which requests application exit"""
    print(HOOK_OUTPUT)
    return data

def test_run_pyscript(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...'

    out, err = run_cmd(base_app, "run_pyscript {}".format(python_script))
    assert expected in out

def test_run_pyscript_recursive_not_allowed(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'recursive.py')
    expected = 'Recursively entering interactive Python shells is not allowed'

    out, err = run_cmd(base_app, "run_pyscript {}".format(python_script))
    assert err[0] == expected

def test_run_pyscript_with_nonexist_file(base_app):
    python_script = 'does_not_exist.py'
    out, err = run_cmd(base_app, "run_pyscript {}".format(python_script))
    assert "Error reading script file" in err[0]

def test_run_pyscript_with_non_python_file(base_app, request):
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'help.txt')
    out, err = run_cmd(base_app, 'run_pyscript {}'.format(filename))
    assert "does not have a .py extension" in err[0]

@pytest.mark.parametrize('python_script', odd_file_names)
def test_run_pyscript_with_odd_file_names(base_app, python_script):
    """
    Pass in file names with various patterns. Since these files don't exist, we will rely
    on the error text to make sure the file names were processed correctly.
    """
    # Mock input to get us passed the warning about not ending in .py
    input_mock = mock.MagicMock(name='input', return_value='1')
    builtins.input = input_mock

    out, err = run_cmd(base_app, "run_pyscript {}".format(utils.quote_string(python_script)))
    err = ''.join(err)
    assert "Error reading script file '{}'".format(python_script) in err

def test_run_pyscript_with_exception(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'raises_exception.py')
    out, err = run_cmd(base_app, "run_pyscript {}".format(python_script))
    assert err[0].startswith('Traceback')
    assert "TypeError: unsupported operand type(s) for +: 'int' and 'str'" in err[-1]

def test_run_pyscript_requires_an_argument(base_app):
    out, err = run_cmd(base_app, "run_pyscript")
    assert "the following arguments are required: script_path" in err[1]

def test_run_pyscript_help(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    out1, err1 = run_cmd(base_app, 'help')
    out2, err2 = run_cmd(base_app, 'run_pyscript {}'.format(python_script))
    assert out1 and out1 == out2

def test_run_pyscript_dir(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'pyscript_dir.py')

    out, err = run_cmd(base_app, 'run_pyscript {}'.format(python_script))
    assert out[0] == "['cmd_echo']"

def test_run_pyscript_stdout_capture(base_app, request):
    base_app.register_cmdfinalization_hook(cmdfinalization_hook)
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'stdout_capture.py')
    out, err = run_cmd(base_app, 'run_pyscript {} {}'.format(python_script, HOOK_OUTPUT))

    assert out[0] == "PASSED"
    assert out[1] == "PASSED"

def test_run_pyscript_stop(base_app, request):
    # Verify onecmd_plus_hooks() returns True if any commands in a pyscript return True for stop
    test_dir = os.path.dirname(request.module.__file__)

    # help.py doesn't run any commands that return True for stop
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    stop = base_app.onecmd_plus_hooks('run_pyscript {}'.format(python_script))
    assert not stop

    # stop.py runs the quit command which does return True for stop
    python_script = os.path.join(test_dir, 'pyscript', 'stop.py')
    stop = base_app.onecmd_plus_hooks('run_pyscript {}'.format(python_script))
    assert stop

def test_run_pyscript_environment(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'environment.py')
    out, err = run_cmd(base_app, 'run_pyscript {}'.format(python_script))

    assert out[0] == "PASSED"

def test_run_pyscript_app_echo(base_app,  request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'echo.py')
    out, err = run_cmd(base_app, 'run_pyscript {}'.format(python_script))

    # Only the edit help text should have been echoed to pytest's stdout
    assert out[0] == "Usage: edit [-h] [file_path]"
