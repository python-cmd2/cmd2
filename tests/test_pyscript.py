# coding=utf-8
# flake8: noqa E302
"""
Unit/functional testing for pytest in cmd2
"""
import os

from .conftest import run_cmd


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
