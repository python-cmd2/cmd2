# coding=utf-8
"""
Cmd2 unit/functional testing

Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import sys

import mock
import pytest

import cmd2
from conftest import run_cmd, normalize, BASE_HELP, HELP_HISTORY, SHORTCUTS_TXT, SHOW_TXT


def test_ver():
    assert cmd2.__version__ == '0.7.0'


def test_base_help(base_app):
    out = run_cmd(base_app, 'help')
    expected = normalize(BASE_HELP)
    assert out == expected


def test_base_help_history(base_app):
    out = run_cmd(base_app, 'help history')
    expected = normalize(HELP_HISTORY)
    assert out == expected


def test_base_shortcuts(base_app):
    out = run_cmd(base_app, 'shortcuts')
    expected = normalize(SHORTCUTS_TXT)
    assert out == expected


def test_base_show(base_app):
    out = run_cmd(base_app, 'show')
    expected = normalize(SHOW_TXT)
    # ignore "editor: vi" (could be others)
    out = [l for l in out if not l.startswith('editor: ')]
    assert out == expected


def test_base_set(base_app):
    out = run_cmd(base_app, 'set quiet True')
    expected = normalize("""
quiet - was: False
now: True
""")
    assert out == expected

    out = run_cmd(base_app, 'show quiet')
    assert out == ['quiet: True']


def test_base_set_not_supported(base_app, capsys):
    run_cmd(base_app, 'set qqq True')
    out, err = capsys.readouterr()
    expected = normalize("""
EXCEPTION of type 'LookupError' occured with message: 'Parameter 'qqq' not supported (type 'show' for list of parameters).'
To enable full traceback, run the following command:  'set debug true'
""")
    assert normalize(str(err)) == expected


def test_base_shell(base_app, monkeypatch):
    m = mock.Mock()
    monkeypatch.setattr("os.system", m)
    out = run_cmd(base_app, 'shell echo a')
    assert out == []
    assert m.called
    m.assert_called_with('echo a')


def test_base_py(base_app, capsys):
    run_cmd(base_app, 'py qqq=3')
    out, err = capsys.readouterr()
    assert out == ''
    run_cmd(base_app, 'py print(qqq)')
    out, err = capsys.readouterr()
    assert out.rstrip() == '3'


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="Unit test doesn't work on win32, but feature does")
def test_base_run_python_script(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...\n'

    run_cmd(base_app, "py run('{}')".format(python_script))
    out, err = capsys.readouterr()
    assert out == expected


def test_base_error(base_app):
    out = run_cmd(base_app, 'meow')
    assert out == ["*** Unknown syntax: meow"]


def test_base_history(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history')
    expected = normalize("""
-------------------------[1]
help
-------------------------[2]
shortcuts
""")
    assert out == expected

    out = run_cmd(base_app, 'history he')
    expected = normalize("""
-------------------------[1]
help
""")
    assert out == expected

    out = run_cmd(base_app, 'history sh')
    expected = normalize("""
-------------------------[2]
shortcuts
""")
    assert out == expected


def test_base_list(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'list')
    expected = normalize("""
-------------------------[2]
shortcuts
""")
    assert out == expected


def test_base_cmdenvironment(base_app):
    out = run_cmd(base_app, 'cmdenvironment')
    expected = normalize("""

        Commands are not case-sensitive.
        Commands may be terminated with: [';']
""")
    assert out[:2] == expected[:2]
    assert out[2].strip().startswith('Settable parameters: ')

    # Settable parameters can be listed in any order, so need to validate carefully using unordered sets
    settable_params = {'continuation_prompt', 'default_file_name', 'prompt', 'abbrev', 'quiet', 'case_insensitive',
                       'colors', 'echo', 'timing', 'editor', 'feedback_to_output', 'debug'}
    out_params = set(out[2].split("Settable parameters: ")[1].split())
    assert settable_params == out_params


def test_base_load(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load {}'.format(filename))

    # But what we can do is check the history to see what commands have been run ...
    out = run_cmd(base_app, 'history')

    # TODO: Figure out why when we unit test the command this way the commands from the script aren't shown in history
    # NOTE: It works correctly when we run it at the command line
    expected = normalize("""
-------------------------[1]
load {}
""".format(filename))
    assert out == expected


def test_base_load_default_file(base_app, capsys):
    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load')
    out, err = capsys.readouterr()

    # The default file 'command.txt' doesn't exist, so we should get an error message
    expected = normalize("""ERROR: Problem accessing script from command.txt:
[Errno 2] No such file or directory: 'command.txt.txt''
To enable full traceback, run the following command:  'set debug true'
""")
    assert normalize(str(err)) == expected


def test_base_relative_load(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, '_relative_load {}'.format(filename))

    # But what we can do is check the history to see what commands have been run ...
    out = run_cmd(base_app, 'history')

    # TODO: Figure out why when we unit test the command this way the commands from the script aren't shown in history
    # NOTE: It works correctly when we run it at the command line
    expected = normalize("""
-------------------------[1]
_relative_load {}
""".format(filename))
    assert out == expected


def test_base_save(base_app, capsys):
    # TODO: Use a temporary directory for the file
    filename = 'deleteme.txt'
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help save')

    # Test the * form of save which saves all commands from history
    run_cmd(base_app, 'save * {}'.format(filename))
    out, err = capsys.readouterr()
    assert out == 'Saved to {}\n'.format(filename)
    expected = normalize("""
help

help save

save * deleteme.txt
""")
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Test the N form of save which saves a numbered command from history
    run_cmd(base_app, 'save 1 {}'.format(filename))
    out, err = capsys.readouterr()
    assert out == 'Saved to {}\n'.format(filename)
    expected = normalize('help')
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Test the blank form of save which saves the most recent command from history
    run_cmd(base_app, 'save {}'.format(filename))
    out, err = capsys.readouterr()
    assert out == 'Saved to {}\n'.format(filename)
    expected = normalize('save 1 {}'.format(filename))
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Delete file that was created
    os.remove(filename)


def test_output_redirection(base_app):
    # TODO: Use a temporary directory/file for this file
    filename = 'out.txt'

    # Verify that writing to a file works
    run_cmd(base_app, 'help > {}'.format(filename))
    expected = normalize(BASE_HELP)
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Verify that appending to a file also works
    run_cmd(base_app, 'help history >> {}'.format(filename))
    expected = normalize(BASE_HELP + '\n' + HELP_HISTORY)
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Delete file that was created
    os.remove(filename)


def test_pipe_to_shell(base_app):
    # Get help on help and pipe it's output to the input of the word count shell command
    out = run_cmd(base_app, 'help help | wc')

    if sys.platform == "win32":
        expected = normalize("1       5      24")
    else:
        expected = normalize("1       5      20")

    assert out[0].strip() == expected[0].strip()


def test_send_to_paste_buffer(base_app):
    from cmd2 import can_clip

    run_cmd(base_app, 'help >')
    expected = normalize(BASE_HELP)

    # If an appropriate tool is installed for reading the contents of the clipboard, then do so
    if can_clip:
        # Read from the clipboard
        try:
            # Python2
            import Tkinter as tk
        except ImportError:
            # Python3
            import tkinter as tk

        root = tk.Tk()
        # keep the window from showing
        root.withdraw()

        # read the clipboard
        c = root.clipboard_get()

        assert normalize(c) == expected


def test_base_timing(base_app, capsys):
    out = run_cmd(base_app, 'set timing True')
    expected = normalize("""timing - was: False
now: True
""")
    assert out == expected
    out, err = capsys.readouterr()
    if sys.platform == 'win32':
        assert out.startswith('Elapsed: 0:00:00')
    else:
        assert out.startswith('Elapsed: 0:00:00.0')


def test_base_debug(base_app, capsys):
    # Try to load a non-existent file with debug set to False by default
    run_cmd(base_app, 'load does_not_exist.txt')
    out, err = capsys.readouterr()
    assert err.startswith('ERROR')

    # Set debug true
    out = run_cmd(base_app, 'set debug True')
    expected = normalize("""
debug - was: False
now: True
""")
    assert out == expected

    # Verify that we now see the exception traceback
    run_cmd(base_app, 'load does_not_exist.txt')
    out, err = capsys.readouterr()
    assert str(err).startswith('Traceback (most recent call last):')


def test_base_colorize(base_app):
    # If using base_app test fixture it won't get colorized because we replaced self.stdout
    color_test = base_app.colorize('Test', 'red')
    assert color_test == 'Test'

    # But if we create a fresh Cmd() instance, it will
    fresh_app = cmd2.Cmd()
    color_test = fresh_app.colorize('Test', 'red')
    assert color_test == '\x1b[31mTest\x1b[39m'

