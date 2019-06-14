# coding=utf-8
# flake8: noqa E302
"""
Cmd2 unit/functional testing
"""
import argparse
import builtins
from code import InteractiveConsole
import io
import os
import sys
import tempfile

from colorama import Fore, Back, Style
import pytest

# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock

import cmd2
from cmd2 import clipboard, constants, utils
from .conftest import run_cmd, normalize, BASE_HELP, BASE_HELP_VERBOSE, \
    HELP_HISTORY, SHORTCUTS_TXT, SHOW_TXT, SHOW_LONG

def CreateOutsimApp():
    c = cmd2.Cmd()
    c.stdout = utils.StdSim(c.stdout)
    return c

@pytest.fixture
def outsim_app():
    return CreateOutsimApp()

def test_version(base_app):
    assert cmd2.__version__

def test_not_in_main_thread(base_app, capsys):
    import threading
    cli_thread = threading.Thread(name='cli_thread', target=base_app.cmdloop)

    cli_thread.start()
    cli_thread.join()
    out, err = capsys.readouterr()
    assert "cmdloop must be run in the main thread" in err

def test_empty_statement(base_app):
    out, err = run_cmd(base_app, '')
    expected = normalize('')
    assert out == expected

def test_base_help(base_app):
    out, err = run_cmd(base_app, 'help')
    expected = normalize(BASE_HELP)
    assert out == expected

def test_base_help_verbose(base_app):
    out, err = run_cmd(base_app, 'help -v')
    expected = normalize(BASE_HELP_VERBOSE)
    assert out == expected

    # Make sure :param type lines are filtered out of help summary
    help_doc = base_app.do_help.__func__.__doc__
    help_doc += "\n:param fake param"
    base_app.do_help.__func__.__doc__ = help_doc

    out, err = run_cmd(base_app, 'help --verbose')
    assert out == expected

def test_base_argparse_help(base_app):
    # Verify that "set -h" gives the same output as "help set" and that it starts in a way that makes sense
    out1, err1 = run_cmd(base_app, 'set -h')
    out2, err2 = run_cmd(base_app, 'help set')

    assert out1 == out2
    assert out1[0].startswith('Usage: set')
    assert out1[1] == ''
    assert out1[2].startswith('Set a settable parameter')

def test_base_invalid_option(base_app):
    out, err = run_cmd(base_app, 'set -z')
    assert err[0] == 'Usage: set [-h] [-a] [-l] [param] [value]'
    assert 'Error: unrecognized arguments: -z' in err[1]

def test_base_shortcuts(base_app):
    out, err = run_cmd(base_app, 'shortcuts')
    expected = normalize(SHORTCUTS_TXT)
    assert out == expected


def test_base_show(base_app):
    # force editor to be 'vim' so test is repeatable across platforms
    base_app.editor = 'vim'
    out, err = run_cmd(base_app, 'set')
    expected = normalize(SHOW_TXT)
    assert out == expected


def test_base_show_long(base_app):
    # force editor to be 'vim' so test is repeatable across platforms
    base_app.editor = 'vim'
    out, err = run_cmd(base_app, 'set -l')
    expected = normalize(SHOW_LONG)
    assert out == expected


def test_base_show_readonly(base_app):
    base_app.editor = 'vim'
    out, err = run_cmd(base_app, 'set -a')
    expected = normalize(SHOW_TXT + '\nRead only settings:' + """
        Commands may be terminated with: {}
        Output redirection and pipes allowed: {}
""".format(base_app.statement_parser.terminators, base_app.allow_redirection))
    assert out == expected


def test_cast():
    # Boolean
    assert utils.cast(True, True) == True
    assert utils.cast(True, False) == False
    assert utils.cast(True, 0) == False
    assert utils.cast(True, 1) == True
    assert utils.cast(True, 'on') == True
    assert utils.cast(True, 'off') == False
    assert utils.cast(True, 'ON') == True
    assert utils.cast(True, 'OFF') == False
    assert utils.cast(True, 'y') == True
    assert utils.cast(True, 'n') == False
    assert utils.cast(True, 't') == True
    assert utils.cast(True, 'f') == False

    # Non-boolean same type
    assert utils.cast(1, 5) == 5
    assert utils.cast(3.4, 2.7) == 2.7
    assert utils.cast('foo', 'bar') == 'bar'
    assert utils.cast([1,2], [3,4]) == [3,4]

def test_cast_problems(capsys):
    expected = 'Problem setting parameter (now {}) to {}; incorrect type?\n'

    # Boolean current, with new value not convertible to bool
    current = True
    new = [True, True]
    assert utils.cast(current, new) == current
    out, err = capsys.readouterr()
    assert out == expected.format(current, new)

    # Non-boolean current, with new value not convertible to current type
    current = 1
    new = 'octopus'
    assert utils.cast(current, new) == current
    out, err = capsys.readouterr()
    assert out == expected.format(current, new)


def test_base_set(base_app):
    out, err = run_cmd(base_app, 'set quiet True')
    expected = normalize("""
quiet - was: False
now: True
""")
    assert out == expected

    out, err = run_cmd(base_app, 'set quiet')
    assert out == ['quiet: True']

def test_set_not_supported(base_app):
    out, err = run_cmd(base_app, 'set qqq True')
    expected = normalize("""
Parameter 'qqq' not supported (type 'set' for list of parameters).
""")
    assert err == expected

def test_set_quiet(base_app):
    out, err = run_cmd(base_app, 'set quie True')
    expected = normalize("""
quiet - was: False
now: True
""")
    assert out == expected

    out, err = run_cmd(base_app, 'set quiet')
    assert out == ['quiet: True']


class OnChangeHookApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _onchange_quiet(self, old, new) -> None:
        """Runs when quiet is changed via set command"""
        self.poutput("You changed quiet")

@pytest.fixture
def onchange_app():
    app = OnChangeHookApp()
    return app

def test_set_onchange_hook(onchange_app):
    out, err = run_cmd(onchange_app, 'set quiet True')
    expected = normalize("""
quiet - was: False
now: True
You changed quiet
""")
    assert out == expected


def test_base_shell(base_app, monkeypatch):
    m = mock.Mock()
    monkeypatch.setattr("{}.Popen".format('subprocess'), m)
    out, err = run_cmd(base_app, 'shell echo a')
    assert out == []
    assert m.called

def test_base_py(base_app):
    # Create a variable and make sure we can see it
    out, err = run_cmd(base_app, 'py qqq=3')
    assert not out

    out, err = run_cmd(base_app, 'py print(qqq)')
    assert out[0].rstrip() == '3'

    # Add a more complex statement
    out, err = run_cmd(base_app, 'py print("spaces" + " in this " + "command")')
    assert out[0].rstrip() == 'spaces in this command'

    # Set locals_in_py to True and make sure we see self
    out, err = run_cmd(base_app, 'set locals_in_py True')
    assert 'now: True' in out

    out, err = run_cmd(base_app, 'py print(self)')
    assert 'cmd2.cmd2.Cmd object' in out[0]

    # Set locals_in_py to False and make sure we can't see self
    out, err = run_cmd(base_app, 'set locals_in_py False')
    assert 'now: False' in out

    out, err = run_cmd(base_app, 'py print(self)')
    assert "NameError: name 'self' is not defined" in err


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="Unit test doesn't work on win32, but feature does")
def test_base_run_python_script(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...'

    out, err = run_cmd(base_app, "py run('{}')".format(python_script))
    assert expected in out


def test_base_run_pyscript(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...'

    out, err = run_cmd(base_app, "pyscript {}".format(python_script))
    assert expected in out

def test_recursive_pyscript_not_allowed(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'scripts', 'recursive.py')
    expected = 'Recursively entering interactive Python consoles is not allowed.'

    out, err = run_cmd(base_app, "pyscript {}".format(python_script))
    assert err[0] == expected

def test_pyscript_with_nonexist_file(base_app):
    python_script = 'does_not_exist.py'
    out, err = run_cmd(base_app, "pyscript {}".format(python_script))
    assert "Error opening script file" in err[0]

def test_pyscript_with_exception(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'scripts', 'raises_exception.py')
    out, err = run_cmd(base_app, "pyscript {}".format(python_script))
    assert err[0].startswith('Traceback')
    assert "TypeError: unsupported operand type(s) for +: 'int' and 'str'" in err[-1]

def test_pyscript_requires_an_argument(base_app):
    out, err = run_cmd(base_app, "pyscript")
    assert "the following arguments are required: script_path" in err[1]


def test_base_error(base_app):
    out, err = run_cmd(base_app, 'meow')
    assert "is not a recognized command" in err[0]


def test_base_load(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Get output out the script
    script_out, script_err = run_cmd(base_app, 'load {}'.format(filename))

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Now run the commands manually and compare their output to script's
    with open(filename, encoding='utf-8') as file:
        script_commands = file.read().splitlines()

    manual_out = []
    manual_err = []
    for cmdline in script_commands:
        out, err = run_cmd(base_app, cmdline)
        manual_out.extend(out)
        manual_err.extend(err)

    assert script_out == manual_out
    assert script_err == manual_err

def test_load_with_empty_args(base_app):
    # The way the load command works, we can't directly capture its stdout or stderr
    out, err = run_cmd(base_app, 'load')

    # The load command requires a file path argument, so we should get an error message
    assert "the following arguments are required" in err[1]


def test_load_with_nonexistent_file(base_app, capsys):
    # The way the load command works, we can't directly capture its stdout or stderr
    out, err = run_cmd(base_app, 'load does_not_exist.txt')

    # The load command requires a path to an existing file
    assert "does not exist" in err[0]

def test_load_with_directory(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    # The way the load command works, we can't directly capture its stdout or stderr
    out, err = run_cmd(base_app, 'load {}'.format(test_dir))

    assert "is not a file" in err[0]

def test_load_with_empty_file(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'empty.txt')

    # The way the load command works, we can't directly capture its stdout or stderr
    out, err = run_cmd(base_app, 'load {}'.format(filename))

    # The load command requires non-empty script files
    assert "is empty" in err[0]


def test_load_with_binary_file(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'binary.bin')

    # The way the load command works, we can't directly capture its stdout or stderr
    out, err = run_cmd(base_app, 'load {}'.format(filename))

    # The load command requires non-empty scripts files
    assert "is not an ASCII or UTF-8 encoded text file" in err[0]


def test_load_with_utf8_file(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'utf8.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Get output out the script
    script_out, script_err = run_cmd(base_app, 'load {}'.format(filename))

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Now run the commands manually and compare their output to script's
    with open(filename, encoding='utf-8') as file:
        script_commands = file.read().splitlines()

    manual_out = []
    manual_err = []
    for cmdline in script_commands:
        out, err = run_cmd(base_app, cmdline)
        manual_out.extend(out)
        manual_err.extend(err)

    assert script_out == manual_out
    assert script_err == manual_err


def test_load_nested_loads(base_app, request):
    # Verify that loading a script with nested load commands works correctly,
    # and loads the nested script commands in the correct order.
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'nested.txt')

    # Load the top level script
    initial_load = 'load ' + filename
    run_cmd(base_app, initial_load)

    # Check that the right commands were executed.
    expected = """
%s
_relative_load precmds.txt
set colors Always
help
shortcuts
_relative_load postcmds.txt
set colors Never""" % initial_load
    out, err = run_cmd(base_app, 'history -s')
    assert out == normalize(expected)


def test_base_runcmds_plus_hooks(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    prefilepath = os.path.join(test_dir, 'scripts', 'precmds.txt')
    postfilepath = os.path.join(test_dir, 'scripts', 'postcmds.txt')

    base_app.runcmds_plus_hooks(['load ' + prefilepath,
                                 'help',
                                 'shortcuts',
                                 'load ' + postfilepath])
    expected = """
load %s
set colors Always
help
shortcuts
load %s
set colors Never""" % (prefilepath, postfilepath)

    out, err = run_cmd(base_app, 'history -s')
    assert out == normalize(expected)

def test_base_relative_load(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Get output out the script
    script_out, script_err = run_cmd(base_app, 'load {}'.format(filename))

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Now run the commands manually and compare their output to script's
    with open(filename, encoding='utf-8') as file:
        script_commands = file.read().splitlines()

    manual_out = []
    manual_err = []
    for cmdline in script_commands:
        out, err = run_cmd(base_app, cmdline)
        manual_out.extend(out)
        manual_err.extend(err)

    assert script_out == manual_out
    assert script_err == manual_err

def test_relative_load_requires_an_argument(base_app):
    out, err = run_cmd(base_app, '_relative_load')
    assert 'Error: the following arguments' in err[1]


def test_output_redirection(base_app):
    fd, filename = tempfile.mkstemp(prefix='cmd2_test', suffix='.txt')
    os.close(fd)

    try:
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
    except:
        raise
    finally:
        os.remove(filename)

def test_output_redirection_to_nonexistent_directory(base_app):
    filename = '~/fakedir/this_does_not_exist.txt'

    # Verify that writing to a file in a non-existent directory doesn't work
    run_cmd(base_app, 'help > {}'.format(filename))
    expected = normalize(BASE_HELP)
    with pytest.raises(FileNotFoundError):
        with open(filename) as f:
            content = normalize(f.read())
        assert content == expected

    # Verify that appending to a file also works
    run_cmd(base_app, 'help history >> {}'.format(filename))
    expected = normalize(BASE_HELP + '\n' + HELP_HISTORY)
    with pytest.raises(FileNotFoundError):
        with open(filename) as f:
            content = normalize(f.read())
        assert content == expected

def test_output_redirection_to_too_long_filename(base_app):
    filename = '~/sdkfhksdjfhkjdshfkjsdhfkjsdhfkjdshfkjdshfkjshdfkhdsfkjhewfuihewiufhweiufhiweufhiuewhiuewhfiuwehfia' \
               'ewhfiuewhfiuewhfiuewhiuewhfiuewhfiuewfhiuwehewiufhewiuhfiweuhfiuwehfiuewfhiuwehiuewfhiuewhiewuhfiueh' \
               'fiuwefhewiuhewiufhewiufhewiufhewiufhewiufhewiufhewiufhewiuhewiufhewiufhewiuheiufhiuewheiwufhewiufheu' \
               'fheiufhieuwhfewiuhfeiufhiuewfhiuewheiwuhfiuewhfiuewhfeiuwfhewiufhiuewhiuewhfeiuwhfiuwehfuiwehfiuehie' \
               'whfieuwfhieufhiuewhfeiuwfhiuefhueiwhfw'

    # Verify that writing to a file in a non-existent directory doesn't work
    run_cmd(base_app, 'help > {}'.format(filename))
    expected = normalize(BASE_HELP)
    with pytest.raises(OSError):
        with open(filename) as f:
            content = normalize(f.read())
        assert content == expected

    # Verify that appending to a file also works
    run_cmd(base_app, 'help history >> {}'.format(filename))
    expected = normalize(BASE_HELP + '\n' + HELP_HISTORY)
    with pytest.raises(OSError):
        with open(filename) as f:
            content = normalize(f.read())
        assert content == expected


def test_feedback_to_output_true(base_app):
    base_app.feedback_to_output = True
    base_app.timing = True
    f, filename = tempfile.mkstemp(prefix='cmd2_test', suffix='.txt')
    os.close(f)

    try:
        run_cmd(base_app, 'help > {}'.format(filename))
        with open(filename) as f:
            content = f.readlines()
        assert content[-1].startswith('Elapsed: ')
    except:
        raise
    finally:
        os.remove(filename)


def test_feedback_to_output_false(base_app):
    base_app.feedback_to_output = False
    base_app.timing = True
    f, filename = tempfile.mkstemp(prefix='feedback_to_output', suffix='.txt')
    os.close(f)

    try:
        out, err = run_cmd(base_app, 'help > {}'.format(filename))

        with open(filename) as f:
            content = f.readlines()
        assert not content[-1].startswith('Elapsed: ')
        assert err[0].startswith('Elapsed')
    except:
        raise
    finally:
        os.remove(filename)


def test_disallow_redirection(base_app):
    # Set allow_redirection to False
    base_app.statement_parser.allow_redirection = False

    filename = 'test_allow_redirect.txt'

    # Verify output wasn't redirected
    out, err = run_cmd(base_app, 'help > {}'.format(filename))
    expected = normalize(BASE_HELP)
    assert out == expected

    # Verify that no file got created
    assert not os.path.exists(filename)

def test_pipe_to_shell(base_app):
    if sys.platform == "win32":
        # Windows
        command = 'help | sort'
    else:
        # Mac and Linux
        # Get help on help and pipe it's output to the input of the word count shell command
        command = 'help help | wc'

    out, err = run_cmd(base_app, command)
    assert out and not err

def test_pipe_to_shell_and_redirect(base_app):
    filename = 'out.txt'
    if sys.platform == "win32":
        # Windows
        command = 'help | sort > {}'.format(filename)
    else:
        # Mac and Linux
        # Get help on help and pipe it's output to the input of the word count shell command
        command = 'help help | wc > {}'.format(filename)

    out, err = run_cmd(base_app, command)
    assert not out and not err
    assert os.path.exists(filename)
    os.remove(filename)

def test_pipe_to_shell_error(base_app):
    # Try to pipe command output to a shell command that doesn't exist in order to produce an error
    out, err = run_cmd(base_app, 'help | foobarbaz.this_does_not_exist')
    assert not out
    assert "Pipe process exited with code" in err[0]

@pytest.mark.skipif(not clipboard.can_clip,
                    reason="Pyperclip could not find a copy/paste mechanism for your system")
def test_send_to_paste_buffer(base_app):
    # Test writing to the PasteBuffer/Clipboard
    run_cmd(base_app, 'help >')
    expected = normalize(BASE_HELP)
    assert normalize(cmd2.cmd2.get_paste_buffer()) == expected

    # Test appending to the PasteBuffer/Clipboard
    run_cmd(base_app, 'help history >>')
    expected = normalize(BASE_HELP + '\n' + HELP_HISTORY)
    assert normalize(cmd2.cmd2.get_paste_buffer()) == expected


def test_base_timing(base_app):
    base_app.feedback_to_output = False
    out, err = run_cmd(base_app, 'set timing True')
    expected = normalize("""timing - was: False
now: True
""")
    assert out == expected

    if sys.platform == 'win32':
        assert err[0].startswith('Elapsed: 0:00:00')
    else:
        assert err[0].startswith('Elapsed: 0:00:00.0')


def _expected_no_editor_error():
    expected_exception = 'OSError'
    # If PyPy, expect a different exception than with Python 3
    if hasattr(sys, "pypy_translation_info"):
        expected_exception = 'EnvironmentError'

    expected_text = normalize("""
EXCEPTION of type '{}' occurred with message: 'Please use 'set editor' to specify your text editing program of choice.'
To enable full traceback, run the following command:  'set debug true'
""".format(expected_exception))

    return expected_text

def test_base_debug(base_app):
    # Purposely set the editor to None
    base_app.editor = None

    # Make sure we get an exception, but cmd2 handles it
    out, err = run_cmd(base_app, 'edit')

    expected = _expected_no_editor_error()
    assert err == expected

    # Set debug true
    out, err = run_cmd(base_app, 'set debug True')
    expected = normalize("""
debug - was: False
now: True
""")
    assert out == expected

    # Verify that we now see the exception traceback
    out, err = run_cmd(base_app, 'edit')
    assert err[0].startswith('Traceback (most recent call last):')

def test_edit_file(base_app, request, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    run_cmd(base_app, 'edit {}'.format(filename))

    # We think we have an editor, so should expect a Popen call
    m.assert_called_once()

def test_edit_file_with_spaces(base_app, request, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'my commands.txt')

    run_cmd(base_app, 'edit "{}"'.format(filename))

    # We think we have an editor, so should expect a Popen call
    m.assert_called_once()

def test_edit_blank(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    run_cmd(base_app, 'edit')

    # We have an editor, so should expect a Popen call
    m.assert_called_once()


def test_base_py_interactive(base_app):
    # Mock out the InteractiveConsole.interact() call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='interact')
    InteractiveConsole.interact = m

    run_cmd(base_app, "py")

    # Make sure our mock was called once and only once
    m.assert_called_once()


def test_base_cmdloop_with_startup_commands():
    intro = 'Hello World, this is an intro ...'

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog", 'quit']
    expected = intro + '\n'

    with mock.patch.object(sys, 'argv', testargs):
        app = CreateOutsimApp()

    app.use_rawinput = True

    # Run the command loop with custom intro
    app.cmdloop(intro=intro)

    out = app.stdout.getvalue()
    assert out == expected


def test_base_cmdloop_without_startup_commands():
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    with mock.patch.object(sys, 'argv', testargs):
        app = CreateOutsimApp()

    app.use_rawinput = True
    app.intro = 'Hello World, this is an intro ...'

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='quit')
    builtins.input = m

    expected = app.intro + '\n'

    # Run the command loop
    app.cmdloop()
    out = app.stdout.getvalue()
    assert out == expected


def test_cmdloop_without_rawinput():
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    with mock.patch.object(sys, 'argv', testargs):
        app = CreateOutsimApp()

    app.use_rawinput = False
    app.echo = False
    app.intro = 'Hello World, this is an intro ...'

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='quit')
    builtins.input = m

    expected = app.intro + '\n'

    with pytest.raises(OSError):
        app.cmdloop()
    out = app.stdout.getvalue()
    assert out == expected

class HookFailureApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # register a postparsing hook method
        self.register_postparsing_hook(self.postparsing_precmd)

    def postparsing_precmd(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Simulate precmd hook failure."""
        data.stop = True
        return data

@pytest.fixture
def hook_failure():
    app = HookFailureApp()
    return app

def test_precmd_hook_success(base_app):
    out = base_app.onecmd_plus_hooks('help')
    assert out is False


def test_precmd_hook_failure(hook_failure):
    out = hook_failure.onecmd_plus_hooks('help')
    assert out is True


class SayApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_say(self, arg):
        self.poutput(arg)

@pytest.fixture
def say_app():
    app = SayApp(allow_cli_args=False)
    app.stdout = utils.StdSim(app.stdout)
    return app

def test_interrupt_quit(say_app):
    say_app.quit_on_sigint = True

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input')
    m.side_effect = ['say hello', KeyboardInterrupt(), 'say goodbye', 'eof']
    builtins.input = m

    try:
        say_app.cmdloop()
    except KeyboardInterrupt:
        pass

    # And verify the expected output to stdout
    out = say_app.stdout.getvalue()
    assert out == 'hello\n'

def test_interrupt_noquit(say_app):
    say_app.quit_on_sigint = False

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input')
    m.side_effect = ['say hello', KeyboardInterrupt(), 'say goodbye', 'eof']
    builtins.input = m

    try:
        say_app.cmdloop()
    except KeyboardInterrupt:
        pass

    # And verify the expected output to stdout
    out = say_app.stdout.getvalue()
    assert out == 'hello\n^C\ngoodbye\n'


class ShellApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_to_shell = True

def test_default_to_shell(base_app, monkeypatch):
    if sys.platform.startswith('win'):
        line = 'dir'
    else:
        line = 'ls'

    base_app.default_to_shell = True
    m = mock.Mock()
    monkeypatch.setattr("{}.Popen".format('subprocess'), m)
    out, err = run_cmd(base_app, line)
    assert out == []
    assert m.called

def test_ansi_prompt_not_esacped(base_app):
    from cmd2.rl_utils import rl_make_safe_prompt
    prompt = '(Cmd) '
    assert rl_make_safe_prompt(prompt) == prompt


def test_ansi_prompt_escaped():
    from cmd2.rl_utils import rl_make_safe_prompt
    app = cmd2.Cmd()
    color = Fore.CYAN
    prompt = 'InColor'
    color_prompt = color + prompt + Fore.RESET

    readline_hack_start = "\x01"
    readline_hack_end = "\x02"

    readline_safe_prompt = rl_make_safe_prompt(color_prompt)
    assert prompt != color_prompt
    if sys.platform.startswith('win'):
        # PyReadline on Windows doesn't suffer from the GNU readline bug which requires the hack
        assert readline_safe_prompt.startswith(color)
        assert readline_safe_prompt.endswith(Fore.RESET)
    else:
        assert readline_safe_prompt.startswith(readline_hack_start + color + readline_hack_end)
        assert readline_safe_prompt.endswith(readline_hack_start + Fore.RESET + readline_hack_end)


class HelpApp(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_squat(self, arg):
        """This docstring help will never be shown because the help_squat method overrides it."""
        pass

    def help_squat(self):
        self.stdout.write('This command does diddly squat...\n')

    def do_edit(self, arg):
        """This overrides the edit command and does nothing."""
        pass

    # This command will be in the "undocumented" section of the help menu
    def do_undoc(self, arg):
        pass

@pytest.fixture
def help_app():
    app = HelpApp()
    return app

def test_custom_command_help(help_app):
    out, err = run_cmd(help_app, 'help squat')
    expected = normalize('This command does diddly squat...')
    assert out == expected

def test_custom_help_menu(help_app):
    out, err = run_cmd(help_app, 'help')
    expected = normalize("""
Documented commands (type help <topic>):
========================================
alias  help     load   py        quit  shell      squat
edit   history  macro  pyscript  set   shortcuts

Undocumented commands:
======================
undoc
""")
    assert out == expected

def test_help_undocumented(help_app):
    out, err = run_cmd(help_app, 'help undoc')
    assert err[0].startswith("No help on undoc")

def test_help_overridden_method(help_app):
    out, err = run_cmd(help_app, 'help edit')
    expected = normalize('This overrides the edit command and does nothing.')
    assert out == expected


class HelpCategoriesApp(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @cmd2.with_category('Some Category')
    def do_diddly(self, arg):
        """This command does diddly"""
        pass

    # This command will be in the "Some Category" section of the help menu even though it has no docstring
    @cmd2.with_category("Some Category")
    def do_cat_nodoc(self, arg):
        pass

    def do_squat(self, arg):
        """This docstring help will never be shown because the help_squat method overrides it."""
        pass

    def help_squat(self):
        self.stdout.write('This command does diddly squat...\n')

    def do_edit(self, arg):
        """This overrides the edit command and does nothing."""
        pass

    cmd2.categorize((do_squat, do_edit), 'Custom Category')

    # This command will be in the "undocumented" section of the help menu
    def do_undoc(self, arg):
        pass

@pytest.fixture
def helpcat_app():
    app = HelpCategoriesApp()
    return app

def test_help_cat_base(helpcat_app):
    out, err = run_cmd(helpcat_app, 'help')
    expected = normalize("""Documented commands (type help <topic>):

Custom Category
===============
edit  squat

Some Category
=============
cat_nodoc  diddly

Other
=====
alias  help  history  load  macro  py  pyscript  quit  set  shell  shortcuts

Undocumented commands:
======================
undoc
""")
    assert out == expected

def test_help_cat_verbose(helpcat_app):
    out, err = run_cmd(helpcat_app, 'help --verbose')
    expected = normalize("""Documented commands (type help <topic>):

Custom Category
================================================================================
edit                This overrides the edit command and does nothing.
squat               This command does diddly squat...

Some Category
================================================================================
cat_nodoc
diddly              This command does diddly

Other
================================================================================
alias               Manage aliases
help                List available commands or provide detailed help for a specific command
history             View, run, edit, save, or clear previously entered commands
load                Run commands in script file that is encoded as either ASCII or UTF-8 text
macro               Manage macros
py                  Invoke Python command or shell
pyscript            Run a Python script file inside the console
quit                Exit this application
set                 Set a settable parameter or show current settings of parameters
shell               Execute a command as if at the OS prompt
shortcuts           List available shortcuts

Undocumented commands:
======================
undoc
""")
    assert out == expected


class SelectApp(cmd2.Cmd):
    def do_eat(self, arg):
        """Eat something, with a selection of sauces to choose from."""
        # Pass in a single string of space-separated selections
        sauce = self.select('sweet salty', 'Sauce? ')
        result = '{food} with {sauce} sauce, yum!'
        result = result.format(food=arg, sauce=sauce)
        self.stdout.write(result + '\n')

    def do_study(self, arg):
        """Learn something, with a selection of subjects to choose from."""
        # Pass in a list of strings for selections
        subject = self.select(['math', 'science'], 'Subject? ')
        result = 'Good luck learning {}!\n'.format(subject)
        self.stdout.write(result)

    def do_procrastinate(self, arg):
        """Waste time in your manner of choice."""
        # Pass in a list of tuples for selections
        leisure_activity = self.select([('Netflix and chill', 'Netflix'), ('Porn', 'WebSurfing')],
                                       'How would you like to procrastinate? ')
        result = 'Have fun procrasinating with {}!\n'.format(leisure_activity)
        self.stdout.write(result)

    def do_play(self, arg):
        """Play your favorite musical instrument."""
        # Pass in an uneven list of tuples for selections
        instrument = self.select([('Guitar', 'Electric Guitar'), ('Drums',)], 'Instrument? ')
        result = 'Charm us with the {}...\n'.format(instrument)
        self.stdout.write(result)

@pytest.fixture
def select_app():
    app = SelectApp()
    return app

def test_select_options(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    food = 'bacon'
    out, err = run_cmd(select_app, "eat {}".format(food))
    expected = normalize("""
   1. sweet
   2. salty
{} with salty sauce, yum!
""".format(food))

    # Make sure our mock was called with the expected arguments
    m.assert_called_once_with('Sauce? ')

    # And verify the expected output to stdout
    assert out == expected

def test_select_invalid_option_too_big(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input')
    # If side_effect is an iterable then each call to the mock will return the next value from the iterable.
    m.side_effect = ['3', '1']  # First pass an invalid selection, then pass a valid one
    builtins.input = m

    food = 'fish'
    out, err = run_cmd(select_app, "eat {}".format(food))
    expected = normalize("""
   1. sweet
   2. salty
'3' isn't a valid choice. Pick a number between 1 and 2:
{} with sweet sauce, yum!
""".format(food))

    # Make sure our mock was called exactly twice with the expected arguments
    arg = 'Sauce? '
    calls = [mock.call(arg), mock.call(arg)]
    m.assert_has_calls(calls)

    # And verify the expected output to stdout
    assert out == expected

def test_select_invalid_option_too_small(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input')
    # If side_effect is an iterable then each call to the mock will return the next value from the iterable.
    m.side_effect = ['0', '1']  # First pass an invalid selection, then pass a valid one
    builtins.input = m

    food = 'fish'
    out, err = run_cmd(select_app, "eat {}".format(food))
    expected = normalize("""
   1. sweet
   2. salty
'0' isn't a valid choice. Pick a number between 1 and 2:
{} with sweet sauce, yum!
""".format(food))

    # Make sure our mock was called exactly twice with the expected arguments
    arg = 'Sauce? '
    calls = [mock.call(arg), mock.call(arg)]
    m.assert_has_calls(calls)

    # And verify the expected output to stdout
    assert out == expected

def test_select_list_of_strings(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    out, err = run_cmd(select_app, "study")
    expected = normalize("""
   1. math
   2. science
Good luck learning {}!
""".format('science'))

    # Make sure our mock was called with the expected arguments
    m.assert_called_once_with('Subject? ')

    # And verify the expected output to stdout
    assert out == expected

def test_select_list_of_tuples(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    out, err = run_cmd(select_app, "procrastinate")
    expected = normalize("""
   1. Netflix
   2. WebSurfing
Have fun procrasinating with {}!
""".format('Porn'))

    # Make sure our mock was called with the expected arguments
    m.assert_called_once_with('How would you like to procrastinate? ')

    # And verify the expected output to stdout
    assert out == expected


def test_select_uneven_list_of_tuples(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    out, err = run_cmd(select_app, "play")
    expected = normalize("""
   1. Electric Guitar
   2. Drums
Charm us with the {}...
""".format('Drums'))

    # Make sure our mock was called with the expected arguments
    m.assert_called_once_with('Instrument? ')

    # And verify the expected output to stdout
    assert out == expected


class HelpNoDocstringApp(cmd2.Cmd):
    greet_parser = argparse.ArgumentParser()
    greet_parser.add_argument('-s', '--shout', action="store_true", help="N00B EMULATION MODE")
    @cmd2.with_argparser_and_unknown_args(greet_parser)
    def do_greet(self, opts, arg):
        arg = ''.join(arg)
        if opts.shout:
            arg = arg.upper()
        self.stdout.write(arg + '\n')

def test_help_with_no_docstring(capsys):
    app = HelpNoDocstringApp()
    app.onecmd_plus_hooks('greet -h')
    out, err = capsys.readouterr()
    assert err == ''
    assert out == """usage: greet [-h] [-s]

optional arguments:
  -h, --help   show this help message and exit
  -s, --shout  N00B EMULATION MODE
"""

@pytest.mark.skipif(sys.platform.startswith('win'),
                    reason="utils.which function only used on Mac and Linux")
def test_which_editor_good():
    import platform
    editor = 'vi'
    path = utils.which(editor)

    if 'azure' in platform.release().lower():
        # vi doesn't exist on VSTS Hosted Linux agents
        assert not path
    else:
        # Assert that the vi editor was found because it should exist on all Mac and Linux systems
        assert path

@pytest.mark.skipif(sys.platform.startswith('win'),
                    reason="utils.which function only used on Mac and Linux")
def test_which_editor_bad():
    nonexistent_editor = 'this_editor_does_not_exist.exe'
    path = utils.which(nonexistent_editor)
    # Assert that the non-existent editor wasn't found
    assert path is None


class MultilineApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, multiline_commands=['orate'], **kwargs)

    orate_parser = argparse.ArgumentParser()
    orate_parser.add_argument('-s', '--shout', action="store_true", help="N00B EMULATION MODE")

    @cmd2.with_argparser_and_unknown_args(orate_parser)
    def do_orate(self, opts, arg):
        arg = ''.join(arg)
        if opts.shout:
            arg = arg.upper()
        self.stdout.write(arg + '\n')

@pytest.fixture
def multiline_app():
    app = MultilineApp()
    return app

def test_multiline_complete_empty_statement_raises_exception(multiline_app):
    with pytest.raises(cmd2.EmptyStatement):
        multiline_app._complete_statement('')

def test_multiline_complete_statement_without_terminator(multiline_app):
    # Mock out the input call so we don't actually wait for a user's response
    # on stdin when it looks for more input
    m = mock.MagicMock(name='input', return_value='\n')
    builtins.input = m

    command = 'orate'
    args = 'hello world'
    line = '{} {}'.format(command, args)
    statement = multiline_app._complete_statement(line)
    assert statement == args
    assert statement.command == command
    assert statement.multiline_command == command

def test_multiline_complete_statement_with_unclosed_quotes(multiline_app):
    # Mock out the input call so we don't actually wait for a user's response
    # on stdin when it looks for more input
    m = mock.MagicMock(name='input', side_effect=['quotes', '" now closed;'])
    builtins.input = m

    line = 'orate hi "partially open'
    statement = multiline_app._complete_statement(line)
    assert statement == 'hi "partially open\nquotes\n" now closed'
    assert statement.command == 'orate'
    assert statement.multiline_command == 'orate'
    assert statement.terminator == ';'

def test_multiline_input_line_to_statement(multiline_app):
    # Verify _input_line_to_statement saves the fully entered input line for multiline commands

    # Mock out the input call so we don't actually wait for a user's response
    # on stdin when it looks for more input
    m = mock.MagicMock(name='input', side_effect=['person', '\n'])
    builtins.input = m

    line = 'orate hi'
    statement = multiline_app._input_line_to_statement(line)
    assert statement.raw == 'orate hi\nperson\n'
    assert statement == 'hi person'
    assert statement.command == 'orate'
    assert statement.multiline_command == 'orate'

def test_clipboard_failure(base_app, capsys):
    # Force cmd2 clipboard to be disabled
    base_app.can_clip = False

    # Redirect command output to the clipboard when a clipboard isn't present
    base_app.onecmd_plus_hooks('help > ')

    # Make sure we got the error output
    out, err = capsys.readouterr()
    assert out == ''
    assert "Cannot redirect to paste buffer; install 'pyperclip' and re-run to enable" in err


class CommandResultApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_affirmative(self, arg):
        self._last_result = cmd2.CommandResult(arg, data=True)

    def do_negative(self, arg):
        self._last_result = cmd2.CommandResult(arg, data=False)

    def do_affirmative_no_data(self, arg):
        self._last_result = cmd2.CommandResult(arg)

    def do_negative_no_data(self, arg):
        self._last_result = cmd2.CommandResult('', arg)

@pytest.fixture
def commandresult_app():
    app = CommandResultApp()
    return app

def test_commandresult_truthy(commandresult_app):
    arg = 'foo'
    run_cmd(commandresult_app, 'affirmative {}'.format(arg))
    assert commandresult_app._last_result
    assert commandresult_app._last_result == cmd2.CommandResult(arg, data=True)

    run_cmd(commandresult_app, 'affirmative_no_data {}'.format(arg))
    assert commandresult_app._last_result
    assert commandresult_app._last_result == cmd2.CommandResult(arg)

def test_commandresult_falsy(commandresult_app):
    arg = 'bar'
    run_cmd(commandresult_app, 'negative {}'.format(arg))
    assert not commandresult_app._last_result
    assert commandresult_app._last_result == cmd2.CommandResult(arg, data=False)

    run_cmd(commandresult_app, 'negative_no_data {}'.format(arg))
    assert not commandresult_app._last_result
    assert commandresult_app._last_result == cmd2.CommandResult('', arg)


def test_is_text_file_bad_input(base_app):
    # Test with a non-existent file
    file_is_valid = utils.is_text_file('does_not_exist.txt')
    assert not file_is_valid

    # Test with a directory
    dir_is_valid = utils.is_text_file('.')
    assert not dir_is_valid


def test_eof(base_app):
    # Only thing to verify is that it returns True
    assert base_app.do_eof('')

def test_echo(capsys):
    app = cmd2.Cmd()
    app.echo = True
    commands = ['help history']

    app.runcmds_plus_hooks(commands)

    out, err = capsys.readouterr()
    assert out.startswith('{}{}\n'.format(app.prompt, commands[0]) + HELP_HISTORY.split()[0])

def test_pseudo_raw_input_tty_rawinput_true():
    # use context managers so original functions get put back when we are done
    # we dont use decorators because we need m_input for the assertion
    with mock.patch('sys.stdin.isatty', mock.MagicMock(name='isatty', return_value=True)):
        with mock.patch('builtins.input', mock.MagicMock(name='input', side_effect=['set', EOFError])) as m_input:
            # run the cmdloop, which should pull input from our mocks
            app = cmd2.Cmd(allow_cli_args=False)
            app.use_rawinput = True
            app._cmdloop()
            # because we mocked the input() call, we won't get the prompt
            # or the name of the command in the output, so we can't check
            # if its there. We assume that if input got called twice, once
            # for the 'set' command, and once for the 'quit' command,
            # that the rest of it worked
            assert m_input.call_count == 2

def test_pseudo_raw_input_tty_rawinput_false():
    # gin up some input like it's coming from a tty
    fakein = io.StringIO(u'{}'.format('set\n'))
    mtty = mock.MagicMock(name='isatty', return_value=True)
    fakein.isatty = mtty
    mreadline = mock.MagicMock(name='readline', wraps=fakein.readline)
    fakein.readline = mreadline

    # run the cmdloop, telling it where to get input from
    app = cmd2.Cmd(stdin=fakein, allow_cli_args=False)
    app.use_rawinput = False
    app._cmdloop()

    # because we mocked the readline() call, we won't get the prompt
    # or the name of the command in the output, so we can't check
    # if its there. We assume that if readline() got called twice, once
    # for the 'set' command, and once for the 'quit' command,
    # that the rest of it worked
    assert mreadline.call_count == 2

# the next helper function and two tests check for piped
# input when use_rawinput is True.
def piped_rawinput_true(capsys, echo, command):
    app = cmd2.Cmd(allow_cli_args=False)
    app.use_rawinput = True
    app.echo = echo
    # run the cmdloop, which should pull input from our mock
    app._cmdloop()
    out, err = capsys.readouterr()
    return app, out

# using the decorator puts the original input function back when this unit test returns
@mock.patch('builtins.input', mock.MagicMock(name='input', side_effect=['set', EOFError]))
def test_pseudo_raw_input_piped_rawinput_true_echo_true(capsys):
    command = 'set'
    app, out = piped_rawinput_true(capsys, True, command)
    out = out.splitlines()
    assert out[0] == '{}{}'.format(app.prompt, command)
    assert out[1].startswith('colors:')

# using the decorator puts the original input function back when this unit test returns
@mock.patch('builtins.input', mock.MagicMock(name='input', side_effect=['set', EOFError]))
def test_pseudo_raw_input_piped_rawinput_true_echo_false(capsys):
    command = 'set'
    app, out = piped_rawinput_true(capsys, False, command)
    firstline = out.splitlines()[0]
    assert firstline.startswith('colors:')
    assert not '{}{}'.format(app.prompt, command) in out

# the next helper function and two tests check for piped
# input when use_rawinput=False
def piped_rawinput_false(capsys, echo, command):
    fakein = io.StringIO(u'{}'.format(command))
    app = cmd2.Cmd(stdin=fakein, allow_cli_args=False)
    app.use_rawinput = False
    app.echo = echo
    app._cmdloop()
    out, err = capsys.readouterr()
    return app, out

def test_pseudo_raw_input_piped_rawinput_false_echo_true(capsys):
    command = 'set'
    app, out = piped_rawinput_false(capsys, True, command)
    out = out.splitlines()
    assert out[0] == '{}{}'.format(app.prompt, command)
    assert out[1].startswith('colors:')

def test_pseudo_raw_input_piped_rawinput_false_echo_false(capsys):
    command = 'set'
    app, out = piped_rawinput_false(capsys, False, command)
    firstline = out.splitlines()[0]
    assert firstline.startswith('colors:')
    assert not '{}{}'.format(app.prompt, command) in out


# other input tests
def test_raw_input(base_app):
    base_app.use_raw_input = True
    fake_input = 'quit'

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.Mock(name='input', return_value=fake_input)
    builtins.input = m

    line = base_app.pseudo_raw_input('(cmd2)')
    assert line == fake_input

def test_stdin_input():
    app = cmd2.Cmd()
    app.use_rawinput = False
    fake_input = 'quit'

    # Mock out the readline call so we don't actually read from stdin
    m = mock.Mock(name='readline', return_value=fake_input)
    app.stdin.readline = m

    line = app.pseudo_raw_input('(cmd2)')
    assert line == fake_input

def test_empty_stdin_input():
    app = cmd2.Cmd()
    app.use_rawinput = False
    fake_input = ''

    # Mock out the readline call so we don't actually read from stdin
    m = mock.Mock(name='readline', return_value=fake_input)
    app.stdin.readline = m

    line = app.pseudo_raw_input('(cmd2)')
    assert line == 'eof'

def test_poutput_string(outsim_app):
    msg = 'This is a test'
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = msg + '\n'
    assert out == expected

def test_poutput_zero(outsim_app):
    msg = 0
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = str(msg) + '\n'
    assert out == expected

def test_poutput_empty_string(outsim_app):
    msg = ''
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = msg
    assert out == expected

def test_poutput_none(outsim_app):
    msg = None
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = ''
    assert out == expected

def test_poutput_color_always(outsim_app):
    msg = 'Hello World'
    color = Fore.CYAN
    outsim_app.colors = 'Always'
    outsim_app.poutput(msg, color=color)
    out = outsim_app.stdout.getvalue()
    expected = color + msg + '\n' + Fore.RESET
    assert out == expected

def test_poutput_color_never(outsim_app):
    msg = 'Hello World'
    color = Fore.CYAN
    outsim_app.colors = 'Never'
    outsim_app.poutput(msg, color=color)
    out = outsim_app.stdout.getvalue()
    expected = msg + '\n'
    assert out == expected


# These are invalid names for aliases and macros
invalid_command_name = [
    '""',  # Blank name
    constants.COMMENT_CHAR,
    '!no_shortcut',
    '">"',
    '"no>pe"',
    '"no spaces"',
    '"nopipe|"',
    '"noterm;"',
    'noembedded"quotes',
]

def test_get_alias_names(base_app):
    assert len(base_app.aliases) == 0
    run_cmd(base_app, 'alias create fake pyscript')
    run_cmd(base_app, 'alias create ls !ls -hal')
    assert len(base_app.aliases) == 2
    assert sorted(base_app.get_alias_names()) == ['fake', 'ls']

def test_get_macro_names(base_app):
    assert len(base_app.macros) == 0
    run_cmd(base_app, 'macro create foo !echo foo')
    run_cmd(base_app, 'macro create bar !echo bar')
    assert len(base_app.macros) == 2
    assert sorted(base_app.get_macro_names()) == ['bar', 'foo']

def test_get_settable_names(base_app):
    assert sorted(base_app.get_settable_names()) == sorted(base_app.settable.keys())

def test_alias_no_subcommand(base_app):
    out, err = run_cmd(base_app, 'alias')
    assert "Usage: alias [-h]" in out[0]

def test_alias_create(base_app):
    # Create the alias
    out, err = run_cmd(base_app, 'alias create fake pyscript')
    assert out == normalize("Alias 'fake' created")

    # Use the alias
    out, err = run_cmd(base_app, 'fake')
    assert "the following arguments are required: script_path" in err[1]

    # See a list of aliases
    out, err = run_cmd(base_app, 'alias list')
    assert out == normalize('alias create fake pyscript')

    # Look up the new alias
    out, err = run_cmd(base_app, 'alias list fake')
    assert out == normalize('alias create fake pyscript')

def test_alias_create_with_quoted_value(base_app):
    """Demonstrate that quotes in alias value will be preserved (except for redirectors and terminators)"""

    # Create the alias
    out, err = run_cmd(base_app, 'alias create fake help ">" "out file.txt" ";"')
    assert out == normalize("Alias 'fake' created")

    # Look up the new alias (Only the redirector should be unquoted)
    out, err = run_cmd(base_app, 'alias list fake')
    assert out == normalize('alias create fake help > "out file.txt" ;')

@pytest.mark.parametrize('alias_name', invalid_command_name)
def test_alias_create_invalid_name(base_app, alias_name, capsys):
    out, err = run_cmd(base_app, 'alias create {} help'.format(alias_name))
    assert "Invalid alias name" in err[0]

def test_alias_create_with_macro_name(base_app):
    macro = "my_macro"
    run_cmd(base_app, 'macro create {} help'.format(macro))
    out, err = run_cmd(base_app, 'alias create {} help'.format(macro))
    assert "Alias cannot have the same name as a macro" in err[0]

def test_alias_that_resolves_into_comment(base_app):
    # Create the alias
    out, err = run_cmd(base_app, 'alias create fake ' + constants.COMMENT_CHAR + ' blah blah')
    assert out == normalize("Alias 'fake' created")

    # Use the alias
    out, err = run_cmd(base_app, 'fake')
    assert not out
    assert not err

def test_alias_list_invalid_alias(base_app):
    # Look up invalid alias
    out, err = run_cmd(base_app, 'alias list invalid')
    assert "Alias 'invalid' not found" in err[0]

def test_alias_delete(base_app):
    # Create an alias
    run_cmd(base_app, 'alias create fake pyscript')

    # Delete the alias
    out, err = run_cmd(base_app, 'alias delete fake')
    assert out == normalize("Alias 'fake' deleted")

def test_alias_delete_all(base_app):
    out, err = run_cmd(base_app, 'alias delete --all')
    assert out == normalize("All aliases deleted")

def test_alias_delete_non_existing(base_app):
    out, err = run_cmd(base_app, 'alias delete fake')
    assert "Alias 'fake' does not exist" in err[0]

def test_alias_delete_no_name(base_app):
    out, err = run_cmd(base_app, 'alias delete')
    assert "Usage: alias delete" in out[0]

def test_multiple_aliases(base_app):
    alias1 = 'h1'
    alias2 = 'h2'
    run_cmd(base_app, 'alias create {} help'.format(alias1))
    run_cmd(base_app, 'alias create {} help -v'.format(alias2))
    out, err = run_cmd(base_app, alias1)
    expected = normalize(BASE_HELP)
    assert out == expected

    out, err = run_cmd(base_app, alias2)
    expected = normalize(BASE_HELP_VERBOSE)
    assert out == expected

def test_macro_no_subcommand(base_app):
    out, err = run_cmd(base_app, 'macro')
    assert "Usage: macro [-h]" in out[0]

def test_macro_create(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake pyscript')
    assert out == normalize("Macro 'fake' created")

    # Use the macro
    out, err = run_cmd(base_app, 'fake')
    assert "the following arguments are required: script_path" in err[1]

    # See a list of macros
    out, err = run_cmd(base_app, 'macro list')
    assert out == normalize('macro create fake pyscript')

    # Look up the new macro
    out, err = run_cmd(base_app, 'macro list fake')
    assert out == normalize('macro create fake pyscript')

def test_macro_create_with_quoted_value(base_app):
    """Demonstrate that quotes in macro value will be preserved (except for redirectors and terminators)"""
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help ">" "out file.txt" ";"')
    assert out == normalize("Macro 'fake' created")

    # Look up the new macro (Only the redirector should be unquoted)
    out, err = run_cmd(base_app, 'macro list fake')
    assert out == normalize('macro create fake help > "out file.txt" ;')

@pytest.mark.parametrize('macro_name', invalid_command_name)
def test_macro_create_invalid_name(base_app, macro_name):
    out, err = run_cmd(base_app, 'macro create {} help'.format(macro_name))
    assert "Invalid macro name" in err[0]

def test_macro_create_with_alias_name(base_app):
    macro = "my_macro"
    run_cmd(base_app, 'alias create {} help'.format(macro))
    out, err = run_cmd(base_app, 'macro create {} help'.format(macro))
    assert "Macro cannot have the same name as an alias" in err[0]

def test_macro_create_with_command_name(base_app):
    out, err = run_cmd(base_app, 'macro create help stuff')
    assert "Macro cannot have the same name as a command" in err[0]

def test_macro_create_with_args(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake {1} {2}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake help -v')
    expected = normalize(BASE_HELP_VERBOSE)
    assert out == expected

def test_macro_create_with_escaped_args(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {{1}}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake')
    assert err[0].startswith('No help on {1}')

def test_macro_usage_with_missing_args(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {1} {2}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake arg1')
    assert "expects at least 2 argument(s)" in err[0]

def test_macro_usage_with_exta_args(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {1}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake alias create')
    assert "Usage: alias create" in out[0]

def test_macro_create_with_missing_arg_nums(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {1} {3}')
    assert "Not all numbers between 1 and 3" in err[0]

def test_macro_create_with_invalid_arg_num(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {1} {-1} {0}')
    assert "Argument numbers must be greater than 0" in err[0]

def test_macro_create_with_unicode_numbered_arg(base_app):
    # Create the macro expecting 1 argument
    out, err = run_cmd(base_app, 'macro create fake help {\N{ARABIC-INDIC DIGIT ONE}}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake')
    assert "expects at least 1 argument(s)" in err[0]

def test_macro_create_with_missing_unicode_arg_nums(base_app):
    out, err = run_cmd(base_app, 'macro create fake help {1} {\N{ARABIC-INDIC DIGIT THREE}}')
    assert "Not all numbers between 1 and 3" in err[0]

def test_macro_that_resolves_into_comment(base_app):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake {1} blah blah')
    assert out == normalize("Macro 'fake' created")

    # Use the macro
    out, err = run_cmd(base_app, 'fake ' + constants.COMMENT_CHAR)
    assert not out
    assert not err

def test_macro_list_invalid_macro(base_app):
    # Look up invalid macro
    out, err = run_cmd(base_app, 'macro list invalid')
    assert "Macro 'invalid' not found" in err[0]

def test_macro_delete(base_app):
    # Create an macro
    run_cmd(base_app, 'macro create fake pyscript')

    # Delete the macro
    out, err = run_cmd(base_app, 'macro delete fake')
    assert out == normalize("Macro 'fake' deleted")

def test_macro_delete_all(base_app):
    out, err = run_cmd(base_app, 'macro delete --all')
    assert out == normalize("All macros deleted")

def test_macro_delete_non_existing(base_app):
    out, err = run_cmd(base_app, 'macro delete fake')
    assert "Macro 'fake' does not exist" in err[0]

def test_macro_delete_no_name(base_app):
    out, err = run_cmd(base_app, 'macro delete')
    assert "Usage: macro delete" in out[0]

def test_multiple_macros(base_app):
    macro1 = 'h1'
    macro2 = 'h2'
    run_cmd(base_app, 'macro create {} help'.format(macro1))
    run_cmd(base_app, 'macro create {} help -v'.format(macro2))
    out, err = run_cmd(base_app, macro1)
    expected = normalize(BASE_HELP)
    assert out == expected

    out, err = run_cmd(base_app, macro2)
    expected = normalize(BASE_HELP_VERBOSE)
    assert out == expected

def test_nonexistent_macro(base_app):
    from cmd2.parsing import StatementParser
    exception = None

    try:
        base_app._resolve_macro(StatementParser().parse('fake'))
    except KeyError as e:
        exception = e

    assert exception is not None


def test_ppaged(outsim_app):
    msg = 'testing...'
    end = '\n'
    outsim_app.ppaged(msg)
    out = outsim_app.stdout.getvalue()
    assert out == msg + end

def test_ppaged_strips_color_when_redirecting(outsim_app):
    msg = 'testing...'
    end = '\n'
    outsim_app.colors = cmd2.constants.COLORS_TERMINAL
    outsim_app.redirecting = True
    outsim_app.ppaged(Fore.RED + msg)
    out = outsim_app.stdout.getvalue()
    assert out == msg + end

def test_ppaged_strips_color_when_redirecting_if_always(outsim_app):
    msg = 'testing...'
    end = '\n'
    outsim_app.colors = cmd2.constants.COLORS_ALWAYS
    outsim_app.redirecting = True
    outsim_app.ppaged(Fore.RED + msg)
    out = outsim_app.stdout.getvalue()
    assert out == Fore.RED + msg + end

# we override cmd.parseline() so we always get consistent
# command parsing by parent methods we don't override
# don't need to test all the parsing logic here, because
# parseline just calls StatementParser.parse_command_only()
def test_parseline_empty(base_app):
    statement = ''
    command, args, line = base_app.parseline(statement)
    assert not command
    assert not args
    assert not line

def test_parseline(base_app):
    statement = " command with 'partially completed quotes  "
    command, args, line = base_app.parseline(statement)
    assert command == 'command'
    assert args == "with 'partially completed quotes"
    assert line == statement.strip()


def test_onecmd_raw_str_continue(outsim_app):
    line = "help"
    stop = outsim_app.onecmd(line)
    out = outsim_app.stdout.getvalue()
    assert not stop
    assert normalize(out) == normalize(BASE_HELP)

def test_onecmd_raw_str_quit(outsim_app):
    line = "quit"
    stop = outsim_app.onecmd(line)
    out = outsim_app.stdout.getvalue()
    assert stop
    assert out == ''


def test_get_all_commands(base_app):
    # Verify that the base app has the expected commands
    commands = base_app.get_all_commands()
    expected_commands = ['_relative_load', 'alias', 'edit', 'eof', 'help', 'history', 'load', 'macro',
                         'py', 'pyscript', 'quit', 'set', 'shell', 'shortcuts']
    assert commands == expected_commands

def test_get_help_topics(base_app):
    # Verify that the base app has no additional help_foo methods
    custom_help = base_app.get_help_topics()
    assert len(custom_help) == 0


class ReplWithExitCode(cmd2.Cmd):
    """ Example cmd2 application where we can specify an exit code when existing."""

    def __init__(self):
        super().__init__(allow_cli_args=False)

    @cmd2.with_argument_list
    def do_exit(self, arg_list) -> bool:
        """Exit the application with an optional exit code.

Usage:  exit [exit_code]
    Where:
        * exit_code - integer exit code to return to the shell
"""
        # If an argument was provided
        if arg_list:
            try:
                self.exit_code = int(arg_list[0])
            except ValueError:
                self.perror("{} isn't a valid integer exit code".format(arg_list[0]))
                self.exit_code = -1

        # Return True to stop the command loop
        return True

    def postloop(self) -> None:
        """Hook method executed once when the cmdloop() method is about to return."""
        self.poutput('exiting with code: {}'.format(self.exit_code))

@pytest.fixture
def exit_code_repl():
    app = ReplWithExitCode()
    app.stdout = utils.StdSim(app.stdout)
    return app

def test_exit_code_default(exit_code_repl):
    app = exit_code_repl
    app.use_rawinput = True

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='exit')
    builtins.input = m

    expected = 'exiting with code: 0\n'

    # Run the command loop
    app.cmdloop()
    out = app.stdout.getvalue()
    assert out == expected

def test_exit_code_nonzero(exit_code_repl):
    app = exit_code_repl
    app.use_rawinput = True

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='exit 23')
    builtins.input = m

    expected = 'exiting with code: 23\n'

    # Run the command loop
    app.cmdloop()
    out = app.stdout.getvalue()
    assert out == expected


class ColorsApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_echo(self, args):
        self.poutput(args)
        self.perror(args, False)

    def do_echo_error(self, args):
        color_on = Fore.RED + Back.BLACK
        color_off = Style.RESET_ALL
        self.poutput(color_on + args + color_off)
        # perror uses colors by default
        self.perror(args, False)

def test_colors_default():
    app = ColorsApp()
    assert app.colors == cmd2.constants.COLORS_TERMINAL

def test_colors_pouterr_always_tty(mocker, capsys):
    app = ColorsApp()
    app.colors = cmd2.constants.COLORS_ALWAYS
    mocker.patch.object(app.stdout, 'isatty', return_value=True)
    mocker.patch.object(sys.stderr, 'isatty', return_value=True)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    # if colors are on, the output should have some escape sequences in it
    assert len(out) > len('oopsie\n')
    assert 'oopsie' in out
    assert len(err) > len('oopsie\n')
    assert 'oopsie' in err

    # but this one shouldn't
    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == 'oopsie\n'
    # errors always have colors
    assert len(err) > len('oopsie\n')
    assert 'oopsie' in err

def test_colors_pouterr_always_notty(mocker, capsys):
    app = ColorsApp()
    app.colors = cmd2.constants.COLORS_ALWAYS
    mocker.patch.object(app.stdout, 'isatty', return_value=False)
    mocker.patch.object(sys.stderr, 'isatty', return_value=False)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    # if colors are on, the output should have some escape sequences in it
    assert len(out) > len('oopsie\n')
    assert 'oopsie' in out
    assert len(err) > len('oopsie\n')
    assert 'oopsie' in err

    # but this one shouldn't
    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == 'oopsie\n'
    # errors always have colors
    assert len(err) > len('oopsie\n')
    assert 'oopsie' in err

def test_colors_terminal_tty(mocker, capsys):
    app = ColorsApp()
    app.colors = cmd2.constants.COLORS_TERMINAL
    mocker.patch.object(app.stdout, 'isatty', return_value=True)
    mocker.patch.object(sys.stderr, 'isatty', return_value=True)

    app.onecmd_plus_hooks('echo_error oopsie')
    # if colors are on, the output should have some escape sequences in it
    out, err = capsys.readouterr()
    assert len(out) > len('oopsie\n')
    assert 'oopsie' in out
    assert len(err) > len('oopsie\n')
    assert 'oopsie' in err

    # but this one shouldn't
    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == 'oopsie\n'
    assert len(err) > len('oopsie\n')
    assert 'oopsie' in err

def test_colors_terminal_notty(mocker, capsys):
    app = ColorsApp()
    app.colors = cmd2.constants.COLORS_TERMINAL
    mocker.patch.object(app.stdout, 'isatty', return_value=False)
    mocker.patch.object(sys.stderr, 'isatty', return_value=False)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

def test_colors_never_tty(mocker, capsys):
    app = ColorsApp()
    app.colors = cmd2.constants.COLORS_NEVER
    mocker.patch.object(app.stdout, 'isatty', return_value=True)
    mocker.patch.object(sys.stderr, 'isatty', return_value=True)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

def test_colors_never_notty(mocker, capsys):
    app = ColorsApp()
    app.colors = cmd2.constants.COLORS_NEVER
    mocker.patch.object(app.stdout, 'isatty', return_value=False)
    mocker.patch.object(sys.stderr, 'isatty', return_value=False)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'


class DisableCommandsApp(cmd2.Cmd):
    """Class for disabling commands"""
    category_name = "Test Category"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @cmd2.with_category(category_name)
    def do_has_help_func(self, arg):
        self.poutput("The real has_help_func")

    def help_has_help_func(self):
        self.poutput('Help for has_help_func')

    @cmd2.with_category(category_name)
    def do_has_no_help_func(self, arg):
        """Help for has_no_help_func"""
        self.poutput("The real has_no_help_func")


@pytest.fixture
def disable_commands_app():
    app = DisableCommandsApp()
    return app


def test_disable_and_enable_category(disable_commands_app):
    # Disable the category
    message_to_print = 'These commands are currently disabled'
    disable_commands_app.disable_category(disable_commands_app.category_name, message_to_print)

    # Make sure all the commands and help on those commands displays the message
    out, err = run_cmd(disable_commands_app, 'has_help_func')
    assert err[0].startswith(message_to_print)

    out, err = run_cmd(disable_commands_app, 'help has_help_func')
    assert err[0].startswith(message_to_print)

    out, err = run_cmd(disable_commands_app, 'has_no_help_func')
    assert err[0].startswith(message_to_print)

    out, err = run_cmd(disable_commands_app, 'help has_no_help_func')
    assert err[0].startswith(message_to_print)

    visible_commands = disable_commands_app.get_visible_commands()
    assert 'has_help_func' not in visible_commands
    assert 'has_no_help_func' not in visible_commands

    # Enable the category
    disable_commands_app.enable_category(disable_commands_app.category_name)

    # Make sure all the commands and help on those commands are restored
    out, err = run_cmd(disable_commands_app, 'has_help_func')
    assert out[0] == "The real has_help_func"

    out, err = run_cmd(disable_commands_app, 'help has_help_func')
    assert out[0] == "Help for has_help_func"

    out, err = run_cmd(disable_commands_app, 'has_no_help_func')
    assert out[0] == "The real has_no_help_func"

    out, err = run_cmd(disable_commands_app, 'help has_no_help_func')
    assert out[0] == "Help for has_no_help_func"

    visible_commands = disable_commands_app.get_visible_commands()
    assert 'has_help_func' in visible_commands
    assert 'has_no_help_func' in visible_commands

def test_enable_enabled_command(disable_commands_app):
    # Test enabling a command that is not disabled
    saved_len = len(disable_commands_app.disabled_commands)
    disable_commands_app.enable_command('has_help_func')

    # The number of disabled_commands should not have changed
    assert saved_len == len(disable_commands_app.disabled_commands)

def test_disable_fake_command(disable_commands_app):
    with pytest.raises(AttributeError):
        disable_commands_app.disable_command('fake', 'fake message')

def test_disable_command_twice(disable_commands_app):
    saved_len = len(disable_commands_app.disabled_commands)
    message_to_print = 'These commands are currently disabled'
    disable_commands_app.disable_command('has_help_func', message_to_print)

    # The length of disabled_commands should have increased one
    new_len = len(disable_commands_app.disabled_commands)
    assert saved_len == new_len - 1
    saved_len = new_len

    # Disable again and the length should not change
    disable_commands_app.disable_command('has_help_func', message_to_print)
    new_len = len(disable_commands_app.disabled_commands)
    assert saved_len == new_len

def test_disabled_command_not_in_history(disable_commands_app):
    message_to_print = 'These commands are currently disabled'
    disable_commands_app.disable_command('has_help_func', message_to_print)

    saved_len = len(disable_commands_app.history)
    run_cmd(disable_commands_app, 'has_help_func')
    assert saved_len == len(disable_commands_app.history)

def test_disabled_message_command_name(disable_commands_app):
    message_to_print = '{} is currently disabled'.format(cmd2.cmd2.COMMAND_NAME)
    disable_commands_app.disable_command('has_help_func', message_to_print)

    out, err = run_cmd(disable_commands_app, 'has_help_func')
    assert err[0].startswith('has_help_func is currently disabled')
