# coding=utf-8
"""
Cmd2 unit/functional testing

Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import sys
import io
import tempfile

import mock
import pytest
import six

from code import InteractiveConsole

# Used for sm.input: raw_input() for Python 2 or input() for Python 3
import six.moves as sm

import cmd2
from conftest import run_cmd, normalize, BASE_HELP, HELP_HISTORY, SHORTCUTS_TXT, SHOW_TXT, SHOW_LONG, StdOut


def test_ver():
    assert cmd2.__version__ == '0.7.8'


def test_empty_statement(base_app):
    out = run_cmd(base_app, '')
    expected = normalize('')
    assert out == expected

def test_base_help(base_app):
    out = run_cmd(base_app, 'help')
    expected = normalize(BASE_HELP)
    assert out == expected


def test_base_help_history(base_app):
    out = run_cmd(base_app, 'help history')
    expected = normalize(HELP_HISTORY)
    assert out == expected

def test_base_options_help(base_app, capsys):
    run_cmd(base_app, 'show -h')
    out, err = capsys.readouterr()
    expected = run_cmd(base_app, 'help show')
    # 'show -h' is the same as 'help show', other than whitespace differences of an extra newline present in 'help show'
    assert normalize(str(out)) == expected

def test_base_invalid_option(base_app, capsys):
    run_cmd(base_app, 'show -z')
    out, err = capsys.readouterr()
    show_help = run_cmd(base_app, 'help show')
    expected = ['no such option: -z']
    expected.extend(show_help)
    # 'show -h' is the same as 'help show', other than whitespace differences of an extra newline present in 'help show'
    assert normalize(str(out)) == expected

def test_base_shortcuts(base_app):
    out = run_cmd(base_app, 'shortcuts')
    expected = normalize(SHORTCUTS_TXT)
    assert out == expected


def test_base_show(base_app):
    # force editor to be 'vim' so test is repeatable across platforms
    base_app.editor = 'vim'
    out = run_cmd(base_app, 'show')
    expected = normalize(SHOW_TXT)
    assert out == expected


def test_base_show_long(base_app):
    # force editor to be 'vim' so test is repeatable across platforms
    base_app.editor = 'vim'
    out = run_cmd(base_app, 'show -l')
    expected = normalize(SHOW_LONG)
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

def test_set_not_supported(base_app, capsys):
    run_cmd(base_app, 'set qqq True')
    out, err = capsys.readouterr()
    expected = normalize("""
EXCEPTION of type 'LookupError' occurred with message: 'Parameter 'qqq' not supported (type 'show' for list of parameters).'
To enable full traceback, run the following command:  'set debug true'
""")
    assert normalize(str(err)) == expected

def test_set_quiet(base_app):
    out = run_cmd(base_app, 'set quie True')
    expected = normalize("""
quiet - was: False
now: True
""")
    assert out == expected

    out = run_cmd(base_app, 'show quiet')
    assert out == ['quiet: True']


def test_base_shell(base_app, monkeypatch):
    m = mock.Mock()
    subprocess = 'subprocess'
    if six.PY2:
        subprocess = 'subprocess32'
    monkeypatch.setattr("{}.Popen".format(subprocess), m)
    out = run_cmd(base_app, 'shell echo a')
    assert out == []
    assert m.called

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


def test_base_run_pyscript(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...\n'

    run_cmd(base_app, "pyscript {}".format(python_script))
    out, err = capsys.readouterr()
    assert out == expected

def test_recursive_pyscript_not_allowed(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'scripts', 'recursive.py')
    expected = 'ERROR: Recursively entering interactive Python consoles is not allowed.\n'

    run_cmd(base_app, "pyscript {}".format(python_script))
    out, err = capsys.readouterr()
    assert err == expected

def test_pyscript_with_nonexist_file(base_app, capsys):
    python_script = 'does_not_exist.py'
    run_cmd(base_app, "pyscript {}".format(python_script))
    out, err = capsys.readouterr()
    assert err.startswith('ERROR: [Errno 2] No such file or directory:')

def test_pyscript_with_exception(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'scripts', 'raises_exception.py')
    run_cmd(base_app, "pyscript {}".format(python_script))
    out, err = capsys.readouterr()
    assert err.startswith('Traceback')
    assert err.endswith("TypeError: unsupported operand type(s) for +: 'int' and 'str'\n")

def test_pyscript_requires_an_argument(base_app, capsys):
    run_cmd(base_app, "pyscript")
    out, err = capsys.readouterr()
    assert err.startswith('ERROR: pyscript command requires at least 1 argument ...')


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

def test_history_script_format(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history -s')
    expected = normalize("""
help
shortcuts
""")
    assert out == expected

def test_history_with_string_argument(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history help')
    expected = normalize("""
-------------------------[1]
help
-------------------------[3]
help history
""")
    assert out == expected


def test_history_with_integer_argument(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history 1')
    expected = normalize("""
-------------------------[1]
help
""")
    assert out == expected


def test_history_with_integer_span(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history 1..2')
    expected = normalize("""
-------------------------[1]
help
-------------------------[2]
shortcuts
""")
    assert out == expected

def test_history_with_span_start(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history 2:')
    expected = normalize("""
-------------------------[2]
shortcuts
-------------------------[3]
help history
""")
    assert out == expected

def test_history_with_span_end(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history :2')
    expected = normalize("""
-------------------------[1]
help
-------------------------[2]
shortcuts
""")
    assert out == expected

def test_history_with_span_index_error(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, '!ls -hal :')
    out = run_cmd(base_app, 'history "hal :"')
    expected = normalize("""
-------------------------[3]
!ls -hal :
""")
    assert out == expected


def test_base_cmdenvironment(base_app):
    out = run_cmd(base_app, 'cmdenvironment')
    expected = normalize("""

        Commands are case-sensitive: {}
        Commands may be terminated with: {}
        Arguments at invocation allowed: {}
        Output redirection and pipes allowed: {}
        Parsing of @options commands:
            Shell lexer mode for command argument splitting: {}
            Strip Quotes after splitting arguments: {}
            Argument type: {}
            
""".format(not base_app.case_insensitive, base_app.terminators, base_app.allow_cli_args, base_app.allow_redirection,
           "POSIX" if cmd2.POSIX_SHLEX else "non-POSIX",
           "True" if cmd2.STRIP_QUOTES_FOR_NON_POSIX and not cmd2.POSIX_SHLEX else "False",
           "List of argument strings" if cmd2.USE_ARG_LIST else "string of space-separated arguments"))
    assert out == expected

def test_base_load(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    assert base_app.cmdqueue == []
    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Run the load command, which populates the command queue and sets the script directory
    run_cmd(base_app, 'load {}'.format(filename))

    assert base_app.cmdqueue == ['help history', 'eos']
    sdir = os.path.dirname(filename)
    assert base_app._script_dir == [sdir]
    assert base_app._current_script_dir == sdir

def test_load_with_empty_args(base_app, capsys):
    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load')
    out, err = capsys.readouterr()

    # The load command requires a file path argument, so we should get an error message
    expected = normalize("""ERROR: load command requires a file path:\n""")
    assert normalize(str(err)) == expected
    assert base_app.cmdqueue == []


def test_load_with_nonexistent_file(base_app, capsys):
    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load does_not_exist.txt')
    out, err = capsys.readouterr()

    # The load command requires a path to an existing file
    assert str(err).startswith("ERROR")
    assert "does not exist or is not a file" in str(err)
    assert base_app.cmdqueue == []


def test_load_with_empty_file(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'empty.txt')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load {}'.format(filename))
    out, err = capsys.readouterr()

    # The load command requires non-empty scripts files
    assert str(err).startswith("ERROR")
    assert "is empty" in str(err)
    assert base_app.cmdqueue == []


def test_load_with_binary_file(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'binary.bin')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load {}'.format(filename))
    out, err = capsys.readouterr()

    # The load command requires non-empty scripts files
    assert str(err).startswith("ERROR")
    assert "is not an ASCII or UTF-8 encoded text file" in str(err)
    assert base_app.cmdqueue == []


def test_load_with_utf8_file(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'utf8.txt')

    assert base_app.cmdqueue == []
    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Run the load command, which populates the command queue and sets the script directory
    run_cmd(base_app, 'load {}'.format(filename))

    assert base_app.cmdqueue == ['!echo γνωρίζω', 'eos']
    sdir = os.path.dirname(filename)
    assert base_app._script_dir == [sdir]
    assert base_app._current_script_dir == sdir


def test_load_nested_loads(base_app, request):
    # Verify that loading a script with nested load commands works correctly,
    # and loads the nested script commands in the correct order. The recursive
    # loads don't happen all at once, but as the commands are interpreted. So,
    # we will need to drain the cmdqueue and inspect the stdout to see if all
    # steps were executed in the expected order.
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'nested.txt')
    assert base_app.cmdqueue == []

    # Load the top level script and then run the command queue until all
    # commands have been exhausted.
    initial_load = 'load ' + filename
    run_cmd(base_app, initial_load)
    while base_app.cmdqueue:
        base_app.onecmd_plus_hooks(base_app.cmdqueue.pop(0))

    # Check that the right commands were executed.
    expected = """
%s
_relative_load precmds.txt
set abbrev on
set colors on
help
shortcuts
_relative_load postcmds.txt
set abbrev off
set colors off""" % initial_load
    assert run_cmd(base_app, 'history -s') == normalize(expected)


def test_base_runcmds_plus_hooks(base_app, request):
    # Make sure that runcmds_plus_hooks works as intended. I.E. to run multiple
    # commands and process any commands added, by them, to the command queue.
    test_dir = os.path.dirname(request.module.__file__)
    prefilepath = os.path.join(test_dir, 'scripts', 'precmds.txt')
    postfilepath = os.path.join(test_dir, 'scripts', 'postcmds.txt')
    assert base_app.cmdqueue == []

    base_app.runcmds_plus_hooks(['load ' + prefilepath,
                                 'help',
                                 'shortcuts',
                                 'load ' + postfilepath])
    expected = """
load %s
set abbrev on
set colors on
help
shortcuts
load %s
set abbrev off
set colors off""" % (prefilepath, postfilepath)
    assert run_cmd(base_app, 'history -s') == normalize(expected)


def test_base_relative_load(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    assert base_app.cmdqueue == []
    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Run the load command, which populates the command queue and sets the script directory
    run_cmd(base_app, '_relative_load {}'.format(filename))

    assert base_app.cmdqueue == ['help history', 'eos']
    sdir = os.path.dirname(filename)
    assert base_app._script_dir == [sdir]
    assert base_app._current_script_dir == sdir

def test_relative_load_requires_an_argument(base_app, capsys):
    run_cmd(base_app, '_relative_load')
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith('ERROR: _relative_load command requires a file path:\n')
    assert base_app.cmdqueue == []


def test_base_save(base_app):
    # TODO: Use a temporary directory for the file
    filename = 'deleteme.txt'
    base_app.feedback_to_output = True
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help save')

    # Test the * form of save which saves all commands from history
    out = run_cmd(base_app, 'save * {}'.format(filename))
    assert out == normalize('Saved to {}\n'.format(filename))
    expected = normalize("""
help

help save

save * deleteme.txt
""")
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Test the N form of save which saves a numbered command from history
    out = run_cmd(base_app, 'save 1 {}'.format(filename))
    assert out == normalize('Saved to {}\n'.format(filename))
    expected = normalize('help')
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Test the blank form of save which saves the most recent command from history
    out = run_cmd(base_app, 'save {}'.format(filename))
    assert out == normalize('Saved to {}\n'.format(filename))
    expected = normalize('save 1 {}'.format(filename))
    with open(filename) as f:
        content = normalize(f.read())
    assert content == expected

    # Delete file that was created
    os.remove(filename)

def test_save_parse_error(base_app, capsys):
    invalid_file = '~!@'
    run_cmd(base_app, 'save {}'.format(invalid_file))
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith('ERROR: Could not understand save target {}\n'.format(invalid_file))

def test_save_tempfile(base_app):
    # Just run help to make sure there is something in the history
    base_app.feedback_to_output = True
    run_cmd(base_app, 'help')
    out = run_cmd(base_app, 'save *')
    output = out[0]
    assert output.startswith('Saved to ')

    # Delete the tempfile which was created
    temp_file = output.split('Saved to ')[1].strip()
    os.remove(temp_file)

def test_save_invalid_history_index(base_app, capsys):
    run_cmd(base_app, 'save 5')
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith("EXCEPTION of type 'IndexError' occurred with message: 'list index out of range'\n")

def test_save_empty_history_and_index(base_app, capsys):
    run_cmd(base_app, 'save')
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith("ERROR: History is empty, nothing to save.\n")

def test_save_invalid_path(base_app, capsys):
    # Just run help to make sure there is something in the history
    run_cmd(base_app, 'help')

    invalid_path = '/no_such_path/foobar.txt'
    run_cmd(base_app, 'save {}'.format(invalid_path))
    out, err = capsys.readouterr()
    assert out == ''
    assert err.startswith("ERROR: Saving '{}' - ".format(invalid_path))


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


def test_feedback_to_output_false(base_app, capsys):
    base_app.feedback_to_output = False
    base_app.timing = True
    f, filename = tempfile.mkstemp(prefix='feedback_to_output', suffix='.txt')
    os.close(f)

    try:
        run_cmd(base_app, 'help > {}'.format(filename))
        out, err = capsys.readouterr()
        with open(filename) as f:
            content = f.readlines()
        assert not content[-1].startswith('Elapsed: ')
        assert err.startswith('Elapsed')
    except:
        raise
    finally:
        os.remove(filename)


def test_allow_redirection(base_app):
    # Set allow_redirection to False
    base_app.allow_redirection = False

    filename = 'test_allow_redirect.txt'

    # Verify output wasn't redirected
    out = run_cmd(base_app, 'help > {}'.format(filename))
    expected = normalize(BASE_HELP)
    assert out == expected

    # Verify that no file got created
    assert not os.path.exists(filename)


def test_input_redirection(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'redirect.txt')

    # NOTE: File 'redirect.txt" contains 1 word "history"

    # Verify that redirecting input ffom a file works
    out = run_cmd(base_app, 'help < {}'.format(filename))
    expected = normalize(HELP_HISTORY)
    assert out == expected


def test_pipe_to_shell(base_app, capsys):
    if sys.platform == "win32":
        # Windows
        command = 'help | sort'
        # Get help menu and pipe it's output to the sort shell command
        # expected = ['', '', '_relative_load  edit  history  py        quit  save  shell      show',
        #             '========================================',
        #             'cmdenvironment  help  load     pyscript  run   set   shortcuts',
        #             'Documented commands (type help <topic>):']
        # assert out == expected
    else:
        # Mac and Linux
        # Get help on help and pipe it's output to the input of the word count shell command
        command = 'help help | wc'
        # # Mac and Linux wc behave the same when piped from shell, but differently when piped stdin from file directly
        # if sys.platform == 'darwin':
        #     expected = "1      11      70"
        # else:
        #     expected = "1 11 70"
        # assert out.strip() == expected.strip()

    run_cmd(base_app, command)
    out, err = capsys.readouterr()

    # Unfortunately with the improved way of piping output to a subprocess, there isn't any good way of getting
    # access to the output produced by that subprocess within a unit test, but we can verify that no error occured
    assert not err

def test_pipe_to_shell_error(base_app, capsys):
    # Try to pipe command output to a shell command that doesn't exist in order to produce an error
    run_cmd(base_app, 'help | foobarbaz.this_does_not_exist')
    out, err = capsys.readouterr()

    assert not out

    expected_error = 'FileNotFoundError'
    if six.PY2:
        if sys.platform.startswith('win'):
            expected_error = 'WindowsError'
        else:
            expected_error = 'OSError'
    assert err.startswith("EXCEPTION of type '{}' occurred with message:".format(expected_error))


@pytest.mark.skipif(not cmd2.can_clip,
                    reason="Pyperclip could not find a copy/paste mechanism for your system")
def test_send_to_paste_buffer(base_app):
    # Test writing to the PasteBuffer/Clipboard
    run_cmd(base_app, 'help >')
    expected = normalize(BASE_HELP)
    assert normalize(cmd2.get_paste_buffer()) == expected

    # Test appending to the PasteBuffer/Clipboard
    run_cmd(base_app, 'help history >>')
    expected = normalize(BASE_HELP + '\n' + HELP_HISTORY)
    assert normalize(cmd2.get_paste_buffer()) == expected


def test_base_timing(base_app, capsys):
    base_app.feedback_to_output = False
    out = run_cmd(base_app, 'set timing True')
    expected = normalize("""timing - was: False
now: True
""")
    assert out == expected
    out, err = capsys.readouterr()
    if sys.platform == 'win32':
        assert err.startswith('Elapsed: 0:00:00')
    else:
        assert err.startswith('Elapsed: 0:00:00.0')


def test_base_debug(base_app, capsys):
    # Try to set a non-existent parameter with debug set to False by default
    run_cmd(base_app, 'set does_not_exist 5')
    out, err = capsys.readouterr()
    assert err.startswith('EXCEPTION')

    # Set debug true
    out = run_cmd(base_app, 'set debug True')
    expected = normalize("""
debug - was: False
now: True
""")
    assert out == expected

    # Verify that we now see the exception traceback
    run_cmd(base_app, 'set does_not_exist 5')
    out, err = capsys.readouterr()
    assert str(err).startswith('Traceback (most recent call last):')


def test_base_colorize(base_app):
    # If using base_app test fixture it won't get colorized because we replaced self.stdout
    color_test = base_app.colorize('Test', 'red')
    assert color_test == 'Test'

    # But if we create a fresh Cmd() instance, it will
    fresh_app = cmd2.Cmd()
    color_test = fresh_app.colorize('Test', 'red')
    # Actually, colorization only ANSI escape codes is only applied on non-Windows systems
    if sys.platform == 'win32':
        assert color_test == 'Test'
    else:
        assert color_test == '\x1b[31mTest\x1b[39m'


def _expected_no_editor_error():
    expected_exception = 'OSError'
    # If using Python 2 or PyPy (either 2 or 3), expect a different exception than with Python 3
    if six.PY2 or hasattr(sys, "pypy_translation_info"):
        expected_exception = 'EnvironmentError'

    expected_text = normalize("""
EXCEPTION of type '{}' occurred with message: 'Please use 'set editor' to specify your text editing program of choice.'
To enable full traceback, run the following command:  'set debug true'
""".format(expected_exception))

    return expected_text

def test_edit_no_editor(base_app, capsys):
    # Purposely set the editor to None
    base_app.editor = None

    # Make sure we get an exception, but cmd2 handles it
    run_cmd(base_app, 'edit')
    out, err = capsys.readouterr()

    expected = _expected_no_editor_error()
    assert normalize(str(err)) == expected

def test_edit_file(base_app, request, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    run_cmd(base_app, 'edit {}'.format(filename))

    # We think we have an editor, so should expect a system call
    m.assert_called_once_with('"{}" "{}"'.format(base_app.editor, filename))

def test_edit_file_with_spaces(base_app, request, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'my commands.txt')

    run_cmd(base_app, 'edit "{}"'.format(filename))

    # We think we have an editor, so should expect a system call
    m.assert_called_once_with('"{}" "{}"'.format(base_app.editor, filename))

def test_edit_blank(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit')

    # We have an editor, so should expect a system call
    m.assert_called_once()

def test_edit_empty_history(base_app, capsys):
    run_cmd(base_app, 'edit')
    out, err = capsys.readouterr()
    assert out == ''
    assert err == 'ERROR: edit must be called with argument if history is empty\n'

def test_edit_valid_positive_number(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit 1')

    # We have an editor, so should expect a system call
    m.assert_called_once()

def test_edit_valid_negative_number(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit "-1"')

    # We have an editor, so should expect a system call
    m.assert_called_once()

def test_edit_invalid_positive_number(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit 23')

    # History index is invalid, so should expect a system call
    m.assert_not_called()

def test_edit_invalid_negative_number(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit "-23"')

    # History index is invalid, so should expect a system call
    m.assert_not_called()


def test_base_py_interactive(base_app):
    # Mock out the InteractiveConsole.interact() call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='interact')
    InteractiveConsole.interact = m

    run_cmd(base_app, "py")

    # Make sure our mock was called once and only once
    m.assert_called_once()


def test_base_cmdloop_with_queue():
    # Create a cmd2.Cmd() instance and make sure basic settings are like we want for test
    app = cmd2.Cmd()
    app.use_rawinput = True
    intro = 'Hello World, this is an intro ...'
    app.cmdqueue.append('quit\n')
    app.stdout = StdOut()

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    expected = intro + '\n'
    with mock.patch.object(sys, 'argv', testargs):
        # Run the command loop with custom intro
        app.cmdloop(intro=intro)
    out = app.stdout.buffer
    assert out == expected


def test_base_cmdloop_without_queue():
    # Create a cmd2.Cmd() instance and make sure basic settings are like we want for test
    app = cmd2.Cmd()
    app.use_rawinput = True
    app.intro = 'Hello World, this is an intro ...'
    app.stdout = StdOut()

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='quit')
    sm.input = m

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    expected = app.intro + '\n'
    with mock.patch.object(sys, 'argv', testargs):
        # Run the command loop
        app.cmdloop()
    out = app.stdout.buffer
    assert out == expected


def test_cmdloop_without_rawinput():
    # Create a cmd2.Cmd() instance and make sure basic settings are like we want for test
    app = cmd2.Cmd()
    app.use_rawinput = False
    app.echo = False
    app.intro = 'Hello World, this is an intro ...'
    app.stdout = StdOut()

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='quit')
    sm.input = m

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    expected = app.intro + '\n'
    with mock.patch.object(sys, 'argv', testargs):
        # Run the command loop
        app.cmdloop()
    out = app.stdout.buffer
    assert out == expected


class HookFailureApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        # Need to use this older form of invoking super class constructor to support Python 2.x and Python 3.x
        cmd2.Cmd.__init__(self, *args, **kwargs)

    def postparsing_precmd(self, statement):
        """Simulate precmd hook failure."""
        return True, statement

@pytest.fixture
def hook_failure():
    app = HookFailureApp()
    app.stdout = StdOut()
    return app

def test_precmd_hook_success(base_app):
    out = base_app.onecmd_plus_hooks('help')
    assert out is None


def test_precmd_hook_failure(hook_failure):
    out = hook_failure.onecmd_plus_hooks('help')
    assert out == True


class ShellApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        # Need to use this older form of invoking super class constructor to support Python 2.x and Python 3.x
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.default_to_shell = True

@pytest.fixture
def shell_app():
    app = ShellApp()
    app.stdout = StdOut()
    return app

def test_default_to_shell_unknown(shell_app):
    unknown_command = 'zyxcw23'
    out = run_cmd(shell_app, unknown_command)
    assert out == ["*** Unknown syntax: {}".format(unknown_command)]

def test_default_to_shell_good(capsys):
    app = cmd2.Cmd()
    app.default_to_shell = True
    if sys.platform.startswith('win'):
        line = 'dir'
    else:
        line = 'ls'
    statement = app.parser_manager.parsed(line)
    retval = app.default(statement)
    assert not retval
    out, err = capsys.readouterr()
    assert out == ''

def test_default_to_shell_failure(capsys):
    app = cmd2.Cmd()
    app.default_to_shell = True
    line = 'ls does_not_exist.xyz'
    statement = app.parser_manager.parsed(line)
    retval = app.default(statement)
    assert not retval
    out, err = capsys.readouterr()
    assert out == "*** Unknown syntax: {}\n".format(line)


def test_ansi_prompt_not_esacped(base_app):
    prompt = '(Cmd) '
    assert base_app._surround_ansi_escapes(prompt) == prompt


def test_ansi_prompt_escaped():
    app = cmd2.Cmd()
    color = 'cyan'
    prompt = 'InColor'
    color_prompt = app.colorize(prompt, color)

    readline_hack_start = "\x01"
    readline_hack_end = "\x02"

    readline_safe_prompt = app._surround_ansi_escapes(color_prompt)
    if sys.platform.startswith('win'):
        # colorize() does nothing on Windows due to lack of ANSI color support
        assert prompt == color_prompt
        assert readline_safe_prompt == prompt
    else:
        assert prompt != color_prompt
        assert readline_safe_prompt.startswith(readline_hack_start + app._colorcodes[color][True] + readline_hack_end)
        assert readline_safe_prompt.endswith(readline_hack_start + app._colorcodes[color][False] + readline_hack_end)


class HelpApp(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""
    def __init__(self, *args, **kwargs):
        # Need to use this older form of invoking super class constructor to support Python 2.x and Python 3.x
        cmd2.Cmd.__init__(self, *args, **kwargs)

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
    app.stdout = StdOut()
    return app

def test_custom_command_help(help_app):
    out = run_cmd(help_app, 'help squat')
    expected = normalize('This command does diddly squat...')
    assert out == expected

def test_custom_help_menu(help_app):
    out = run_cmd(help_app, 'help')
    expected = normalize("""
Documented commands (type help <topic>):
========================================
_relative_load  edit  history  py        quit  save  shell      show
cmdenvironment  help  load     pyscript  run   set   shortcuts  squat

Undocumented commands:
======================
undoc
""")
    assert out == expected

def test_help_undocumented(help_app):
    out = run_cmd(help_app, 'help undoc')
    expected = normalize('*** No help on undoc')
    assert out == expected

def test_help_overridden_method(help_app):
    out = run_cmd(help_app, 'help edit')
    expected = normalize('This overrides the edit command and does nothing.')
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
    app.stdout = StdOut()
    return app

def test_select_options(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='2')
    sm.input = m

    food = 'bacon'
    out = run_cmd(select_app, "eat {}".format(food))
    expected = normalize("""
   1. sweet
   2. salty
{} with salty sauce, yum!
""".format(food))

    # Make sure our mock was called with the expected arguments
    m.assert_called_once_with('Sauce? ')

    # And verify the expected output to stdout
    assert out == expected

def test_select_invalid_option(select_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input')
    # If side_effect is an iterable then each call to the mock will return the next value from the iterable.
    m.side_effect = ['3', '1']  # First pass and invalid selection, then pass a valid one
    sm.input = m

    food = 'fish'
    out = run_cmd(select_app, "eat {}".format(food))
    expected = normalize("""
   1. sweet
   2. salty
3 isn't a valid choice. Pick a number between 1 and 2:
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
    sm.input = m

    out = run_cmd(select_app, "study")
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
    sm.input = m

    out = run_cmd(select_app, "procrastinate")
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
    sm.input = m

    out = run_cmd(select_app, "play")
    expected = normalize("""
   1. Electric Guitar
   2. Drums
Charm us with the {}...
""".format('Drums'))

    # Make sure our mock was called with the expected arguments
    m.assert_called_once_with('Instrument? ')

    # And verify the expected output to stdout
    assert out == expected

@pytest.fixture
def noarglist_app():
    cmd2.set_use_arg_list(False)
    app = cmd2.Cmd()
    app.stdout = StdOut()
    return app

def test_pyscript_with_noarglist(noarglist_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, '..', 'examples', 'scripts', 'arg_printer.py')
    expected = """Running Python script 'arg_printer.py' which was called with 2 arguments
arg 1: 'foo'
arg 2: 'bar'
"""
    run_cmd(noarglist_app, 'pyscript {} foo bar'.format(python_script))
    out, err = capsys.readouterr()
    assert out == expected


class OptionApp(cmd2.Cmd):
    @cmd2.options([cmd2.make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE")])
    def do_greet(self, arg, opts=None):
        arg = ''.join(arg)
        if opts.shout:
            arg = arg.upper()
        self.stdout.write(arg + '\n')

def test_option_help_with_no_docstring(capsys):
    app = OptionApp()
    app.onecmd_plus_hooks('greet -h')
    out, err = capsys.readouterr()
    assert err == ''
    assert out == """Usage: greet [options] arg

Options:
  -h, --help   show this help message and exit
  -s, --shout  N00B EMULATION MODE
"""

@pytest.mark.skipif(sys.platform.startswith('win'),
                    reason="cmd2._which function only used on Mac and Linux")
def test_which_editor_good():
    editor = 'vi'
    path = cmd2._which(editor)
    # Assert that the vi editor was found because it should exist on all Mac and Linux systems
    assert path

@pytest.mark.skipif(sys.platform.startswith('win'),
                    reason="cmd2._which function only used on Mac and Linux")
def test_which_editor_bad():
    editor = 'notepad.exe'
    path = cmd2._which(editor)
    # Assert that the editor wasn't found because no notepad.exe on non-Windows systems ;-)
    assert path is None


class MultilineApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        self.multilineCommands = ['orate']

        # Need to use this older form of invoking super class constructor to support Python 2.x and Python 3.x
        cmd2.Cmd.__init__(self, *args, **kwargs)

    @cmd2.options([cmd2.make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE")])
    def do_orate(self, arg, opts=None):
        arg = ''.join(arg)
        if opts.shout:
            arg = arg.upper()
        self.stdout.write(arg + '\n')

@pytest.fixture
def multiline_app():
    app = MultilineApp()
    app.stdout = StdOut()
    return app

def test_multiline_complete_empty_statement_raises_exception(multiline_app):
    with pytest.raises(cmd2.EmptyStatement):
        multiline_app._complete_statement('')

def test_multiline_complete_statement_without_terminator(multiline_app):
    # Mock out the input call so we don't actually wait for a user's response on stdin when it looks for more input
    m = mock.MagicMock(name='input', return_value='\n')
    sm.input = m

    command = 'orate'
    args = 'hello world'
    line = '{} {}'.format(command, args)
    statement = multiline_app._complete_statement(line)
    assert statement == args
    assert statement.parsed.command == command


def test_clipboard_failure(capsys):
    # Force cmd2 clipboard to be disabled
    cmd2.can_clip = False
    app = cmd2.Cmd()

    # Redirect command output to the clipboard when a clipboard isn't present
    app.onecmd_plus_hooks('help > ')

    # Make sure we got the error output
    out, err = capsys.readouterr()
    assert out == ''
    assert 'Cannot redirect to paste buffer; install ``xclip`` and re-run to enable' in err


def test_run_command_with_empty_arg(base_app):
    command = 'help'
    base_app.feedback_to_output = True
    run_cmd(base_app, command)
    out = run_cmd(base_app, 'run')
    expected = normalize('{}\n\n'.format(command) + BASE_HELP)
    assert out == expected

def test_run_command_with_empty_history(base_app):
    base_app.feedback_to_output = True
    out = run_cmd(base_app, 'run')
    assert out == []


class CmdResultApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs):
        # Need to use this older form of invoking super class constructor to support Python 2.x and Python 3.x
        cmd2.Cmd.__init__(self, *args, **kwargs)

    def do_affirmative(self, arg):
        self._last_result = cmd2.CmdResult(arg)

    def do_negative(self, arg):
        self._last_result = cmd2.CmdResult('', arg)

@pytest.fixture
def cmdresult_app():
    app = CmdResultApp()
    app.stdout = StdOut()
    return app

def test_cmdresult(cmdresult_app):
    arg = 'foo'
    run_cmd(cmdresult_app, 'affirmative {}'.format(arg))
    assert cmdresult_app._last_result
    assert cmdresult_app._last_result == cmd2.CmdResult(arg)

    arg = 'bar'
    run_cmd(cmdresult_app, 'negative {}'.format(arg))
    assert not cmdresult_app._last_result
    assert cmdresult_app._last_result == cmd2.CmdResult('', arg)


@pytest.fixture
def abbrev_app():
    app = cmd2.Cmd()
    app.abbrev = True
    app.stdout = StdOut()
    return app

def test_exclude_from_history(abbrev_app, monkeypatch):
    # Run all variants of run
    run_cmd(abbrev_app, 'run')
    run_cmd(abbrev_app, 'ru')
    run_cmd(abbrev_app, 'r')

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    monkeypatch.setattr("os.system", m)

    # Run all variants of edit
    run_cmd(abbrev_app, 'edit')
    run_cmd(abbrev_app, 'edi')
    run_cmd(abbrev_app, 'ed')

    # Run all variants of history
    run_cmd(abbrev_app, 'history')
    run_cmd(abbrev_app, 'histor')
    run_cmd(abbrev_app, 'histo')
    run_cmd(abbrev_app, 'hist')
    run_cmd(abbrev_app, 'his')
    run_cmd(abbrev_app, 'hi')

    # Verify that the history is empty
    out = run_cmd(abbrev_app, 'history')
    assert out == []

    # Now run a command which isn't excluded from the history
    run_cmd(abbrev_app, 'help')
    # And verify we have a history now ...
    out = run_cmd(abbrev_app, 'history')
    expected = normalize("""-------------------------[1]
help""")
    assert out == expected


def test_is_text_file_bad_input(base_app):
    # Test with a non-existent file
    file_is_valid = base_app.is_text_file('does_not_exist.txt')
    assert not file_is_valid

    # Test with a directory
    dir_is_valid = base_app.is_text_file('.')
    assert not dir_is_valid


def test_eof(base_app):
    # Only thing to verify is that it returns True
    assert base_app.do_eof('dont care')

def test_eos(base_app):
    sdir = 'dummy_dir'
    base_app._script_dir.append(sdir)
    assert len(base_app._script_dir) == 1

    # Assert that it does NOT return true
    assert not base_app.do_eos('dont care')

    # And make sure it reduced the length of the script dir list
    assert len(base_app._script_dir) == 0

def test_echo(capsys):
    app = cmd2.Cmd()
    # Turn echo on and pre-stage some commands in the queue, simulating like we are in the middle of a script
    app.echo = True
    command = 'help history'
    app.cmdqueue = [command, 'quit', 'eos']
    app._script_dir.append('some_dir')

    assert app._current_script_dir is not None

    # Run the inner _cmdloop
    app._cmdloop()

    out, err = capsys.readouterr()

    # Check the output
    assert app.cmdqueue == []
    assert app._current_script_dir is None
    assert out.startswith('{}{}\n'.format(app.prompt, command) + 'history [arg]: lists past commands issued')

def test_pseudo_raw_input_tty_rawinput_true():
    # use context managers so original functions get put back when we are done
    # we dont use decorators because we need m_input for the assertion
    with mock.patch('sys.stdin.isatty',
            mock.MagicMock(name='isatty', return_value=True)):
        with mock.patch('six.moves.input',
                mock.MagicMock(name='input', side_effect=['set', EOFError])) as m_input:
            # run the cmdloop, which should pull input from our mocks
            app = cmd2.Cmd()
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
    app = cmd2.Cmd(stdin=fakein)
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
    app = cmd2.Cmd()
    app.use_rawinput = True
    app.echo = echo
    # run the cmdloop, which should pull input from our mock
    app._cmdloop()
    out, err = capsys.readouterr()
    return (app, out)

# using the decorator puts the original function at six.moves.input
# back when this method returns
@mock.patch('six.moves.input',
        mock.MagicMock(name='input', side_effect=['set', EOFError]))
def test_pseudo_raw_input_piped_rawinput_true_echo_true(capsys):
    command = 'set'
    app, out = piped_rawinput_true(capsys, True, command)
    out = out.splitlines()
    assert out[0] == '{}{}'.format(app.prompt, command)
    assert out[1] == 'abbrev: False'

# using the decorator puts the original function at six.moves.input
# back when this method returns
@mock.patch('six.moves.input',
        mock.MagicMock(name='input', side_effect=['set', EOFError]))
def test_pseudo_raw_input_piped_rawinput_true_echo_false(capsys):
    command = 'set'
    app, out = piped_rawinput_true(capsys, False, command)
    firstline = out.splitlines()[0]
    assert firstline == 'abbrev: False'
    assert not '{}{}'.format(app.prompt, command) in out

# the next helper function and two tests check for piped
# input when use_rawinput=False
def piped_rawinput_false(capsys, echo, command):
    fakein = io.StringIO(u'{}'.format(command))
    # run the cmdloop, telling it where to get input from
    app = cmd2.Cmd(stdin=fakein)
    app.use_rawinput = False
    app.echo = echo
    app.abbrev = False
    app._cmdloop()
    out, err = capsys.readouterr()
    return (app, out)

def test_pseudo_raw_input_piped_rawinput_false_echo_true(capsys):
    command = 'set'
    app, out = piped_rawinput_false(capsys, True, command)
    out = out.splitlines()
    assert out[0] == '{}{}'.format(app.prompt, command)
    assert out[1] == 'abbrev: False'

def test_pseudo_raw_input_piped_rawinput_false_echo_false(capsys):
    command = 'set'
    app, out = piped_rawinput_false(capsys, False, command)
    firstline = out.splitlines()[0]
    assert firstline == 'abbrev: False'
    assert not '{}{}'.format(app.prompt, command) in out

#
# other input tests
def test_raw_input(base_app):
    base_app.use_raw_input = True
    fake_input = 'quit'

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.Mock(name='input', return_value=fake_input)
    sm.input = m

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


def test_poutput_string(base_app):
    msg = 'This is a test'
    base_app.poutput(msg)
    out = base_app.stdout.buffer
    expected = msg + '\n'
    assert out == expected

def test_poutput_zero(base_app):
    msg = 0
    base_app.poutput(msg)
    out = base_app.stdout.buffer
    expected = str(msg) + '\n'
    assert out == expected

def test_poutput_empty_string(base_app):
    msg = ''
    base_app.poutput(msg)
    out = base_app.stdout.buffer
    expected = msg
    assert out == expected

def test_poutput_none(base_app):
    msg = None
    base_app.poutput(msg)
    out = base_app.stdout.buffer
    expected = ''
    assert out == expected
