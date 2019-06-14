# coding=utf-8
# flake8: noqa E302
"""
Unit/functional testing for pytest in cmd2
"""
import os
from cmd2 import plugin

from .conftest import run_cmd

HOOK_OUTPUT = "TEST_OUTPUT"

def cmdfinalization_hook(data: plugin.CommandFinalizationData) -> plugin.CommandFinalizationData:
    """A cmdfinalization_hook hook which requests application exit"""
    print(HOOK_OUTPUT)
    return data

def test_pyscript_help(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    out1, err1 = run_cmd(base_app, 'help')
    out2, err2 = run_cmd(base_app, 'pyscript {}'.format(python_script))
    assert out1 and out1 == out2


def test_pyscript_dir(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'pyscript_dir.py')

    out, err = run_cmd(base_app, 'pyscript {}'.format(python_script))
    assert out
    assert out[0] == "['cmd_echo']"


def test_pyscript_stdout_capture(base_app, request):
    base_app.register_cmdfinalization_hook(cmdfinalization_hook)
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'stdout_capture.py')
    out, err = run_cmd(base_app, 'pyscript {} {}'.format(python_script, HOOK_OUTPUT))

    assert out[0] == "PASSED"
    assert out[1] == "PASSED"

def test_pyscript_stop(base_app, request):
    # Verify onecmd_plus_hooks() returns True if any commands in a pyscript return True for stop
    test_dir = os.path.dirname(request.module.__file__)

    # help.py doesn't run any commands that returns True for stop
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    stop = base_app.onecmd_plus_hooks('pyscript {}'.format(python_script))
    assert not stop

    # stop.py runs the quit command which does return True for stop
    python_script = os.path.join(test_dir, 'pyscript', 'stop.py')
    stop = base_app.onecmd_plus_hooks('pyscript {}'.format(python_script))
    assert stop
