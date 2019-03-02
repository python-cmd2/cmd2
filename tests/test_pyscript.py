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
    expected = run_cmd(base_app, 'help')

    assert len(expected) > 0
    assert len(expected[0]) > 0
    out = run_cmd(base_app, 'pyscript {}'.format(python_script))
    assert len(out) > 0
    assert out == expected


def test_pyscript_dir(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'pyscript_dir.py')

    run_cmd(base_app, 'pyscript {}'.format(python_script))
    out, _ = capsys.readouterr()
    out = out.strip()
    assert len(out) > 0
    assert out == "['cmd_echo']"
