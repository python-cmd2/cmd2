#
# Cmd2 unit/functional testing
#
# Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
# Released under MIT license, see LICENSE file

import mock
import pytest

from conftest import run_cmd, _normalize
import cmd2

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


def test_ver():
    assert cmd2.__version__ == '0.6.9a'


def test_base_help(base_app):
    out = run_cmd(base_app, 'help')
    expected = _normalize("""
Documented commands (type help <topic>):
========================================
_load           ed    history  list   py   save   shortcuts
_relative_load  edit  l        load   r    set    show
cmdenvironment  hi    li       pause  run  shell

Undocumented commands:
======================
EOF  eof  exit  help  q  quit
""")
    assert out == expected


def test_base_help_history(base_app):
    out = run_cmd(base_app, 'help history')
    expected = _normalize("""
history [arg]: lists past commands issued

        | no arg:         list all
        | arg is integer: list one history item, by index
        | arg is string:  string search
        | arg is /enclosed in forward-slashes/: regular expression search

Usage: history [options] (limit on which commands to include)

Options:
  -h, --help    show this help message and exit
  -s, --script  Script format; no separation lines
""")
    assert out == expected


def test_base_shortcuts(base_app):
    out = run_cmd(base_app, 'shortcuts')
    expected = _normalize("""
Single-key shortcuts for other commands:
!: shell
?: help
@: load
@@: _relative_load
""")
    assert out == expected


def notest_base_(base_app):
    out = run_cmd(base_app, 'shortcuts')
    expected = _normalize("""
""")
    assert out == expected


def test_base_show(base_app):
    out = run_cmd(base_app, 'show')
    expected = _normalize("""
abbrev: True
case_insensitive: True
colors: True
continuation_prompt: >
debug: False
default_file_name: command.txt
echo: False
feedback_to_output: False
prompt: (Cmd)
quiet: False
timing: False
""")
    # ignore "editor: vi" (could be others)
    out = [l for l in out if not l.startswith('editor: ')]
    assert out == expected


def test_base_set(base_app):
    out = run_cmd(base_app, 'set quiet True')
    expected = _normalize("""
quiet - was: False
now: True
""")
    assert out == expected

    out = run_cmd(base_app, 'show quiet')
    assert out == ['quiet: True']


def test_base_set_not_supported(base_app):
    out = run_cmd(base_app, 'set qqq True')
    assert out == []
    # TODO: check stderr


def test_base_shell(base_app, monkeypatch):
    m = mock.Mock()
    monkeypatch.setattr("os.system", m)
    out = run_cmd(base_app, 'shell echo a')
    assert out == []
    assert m.called
    m.assert_called_with('echo a')


def test_base_py(base_app):
    out = run_cmd(base_app, 'py qqq=3')
    assert out == []
    out = run_cmd(base_app, 'py print qqq')
    assert out == []
    # TODO: check stderr


def test_base_error(base_app):
    out = run_cmd(base_app, 'meow')
    assert out == ["*** Unknown syntax: meow"]


def test_base_history(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history')
    expected = _normalize("""
-------------------------[1]
help
-------------------------[2]
shortcuts
""")
    assert out == expected

    out = run_cmd(base_app, 'history he')
    expected = _normalize("""
-------------------------[1]
help
""")
    assert out == expected

    out = run_cmd(base_app, 'history sh')
    expected = _normalize("""
-------------------------[2]
shortcuts
""")
    assert out == expected


def test_base_list(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'list')
    expected = _normalize("""
-------------------------[2]
shortcuts
""")
    assert out == expected


@pytest.mark.xfail
def test_base_load(base_app):
    base_app.read_file_or_url = mock.Mock(
        return_value=StringIO('set quiet True\n')
    )
    out = run_cmd(base_app, 'load myfname')
    expected = _normalize("""
quiet - was: False
now: True
""")
    assert out == expected


