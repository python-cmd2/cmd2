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
import six

from code import InteractiveConsole

# Used for sm.input: raw_input() for Python 2 or input() for Python 3
import six.moves as sm

import cmd2
from conftest import run_cmd, normalize, BASE_HELP, HELP_HISTORY, SHORTCUTS_TXT, SHOW_TXT, SHOW_LONG, StdOut


def test_ver():
    assert cmd2.__version__ == '0.7.4'


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


def test_base_set_not_supported(base_app, capsys):
    run_cmd(base_app, 'set qqq True')
    out, err = capsys.readouterr()
    expected = normalize("""
EXCEPTION of type 'LookupError' occurred with message: 'Parameter 'qqq' not supported (type 'show' for list of parameters).'
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


@pytest.mark.skipif(sys.platform == 'win32',
                    reason="Unit test doesn't work on win32, but feature does")
def test_base_run_pyscript(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...\n'

    run_cmd(base_app, "pyscript {}".format(python_script))
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


def test_base_load_with_empty_args(base_app, capsys):
    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load')
    out, err = capsys.readouterr()

    # The load command requires a file path argument, so we should get an error message
    expected = normalize("""ERROR: load command requires a file path:\n""")
    assert normalize(str(err)) == expected


def test_base_load_with_nonexistent_file(base_app, capsys):
    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load does_not_exist.txt')
    out, err = capsys.readouterr()

    # The load command requires a path to an existing file
    assert str(err).startswith("ERROR")
    assert "does not exist or is not a file" in str(err)


def test_base_load_with_empty_file(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'empty.txt')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load {}'.format(filename))
    out, err = capsys.readouterr()

    # The load command requires non-empty scripts files
    assert str(err).startswith("ERROR")
    assert "is empty" in str(err)


def test_base_load_with_binary_file(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'binary.bin')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load {}'.format(filename))
    out, err = capsys.readouterr()

    # The load command requires non-empty scripts files
    assert str(err).startswith("ERROR")
    assert "is not an ASCII or UTF-8 encoded text file" in str(err)


def test_base_load_with_utf8_file(base_app, capsys, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'utf8.txt')

    # The way the load command works, we can't directly capture its stdout or stderr
    run_cmd(base_app, 'load {}'.format(filename))
    out, err = capsys.readouterr()

    # TODO Make this test better once shell command is fixed to used cmd2's stdout
    assert str(err) == ''


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


def test_base_save(base_app):
    # TODO: Use a temporary directory for the file
    filename = 'deleteme.txt'
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

    # Verify that redirecting input from a file works
    out = run_cmd(base_app, 'help < {}'.format(filename))
    expected = normalize(HELP_HISTORY)
    assert out == expected


def test_pipe_to_shell(base_app):
    if sys.platform == "win32":
        # Windows
        # Get help menu and pipe it's output to the sort shell command
        out = run_cmd(base_app, 'help | sort')
        expected = ['', '', '_relative_load  edit  history  pause  pyscript  run   set    shortcuts',
                    '========================================',
                    'cmdenvironment  help  load     py     quit      save  shell  show',
                    'Documented commands (type help <topic>):']
        assert out == expected
    else:
        # Mac and Linux
        # Get help on help and pipe it's output to the input of the word count shell command
        out = run_cmd(base_app, 'help help | wc')

        # Mac and Linux wc behave the same when piped from shell, but differently when piped stdin from file directly
        if sys.platform == 'darwin':
            expected = normalize("1      11      70")
        else:
            expected = normalize("1 11 70")
        assert out[0].strip() == expected[0].strip()


@pytest.mark.skipif(not cmd2.can_clip,
                    reason="Pyperclip could not find a copy/paste mechanism for your system")
def test_send_to_paste_buffer(base_app):
    from cmd2 import can_clip

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
        assert out.startswith('Elapsed: 0:00:00')
    else:
        assert out.startswith('Elapsed: 0:00:00.0')


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
    run_cmd(base_app, 'ed')
    out, err = capsys.readouterr()

    expected = _expected_no_editor_error()
    assert normalize(str(err)) == expected


def test_edit_file(base_app, request):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    os.system = m

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    run_cmd(base_app, 'edit {}'.format(filename))

    # We think we have an editor, so should expect a system call
    m.assert_called_once_with('{} {}'.format(base_app.editor, filename))


def test_edit_number(base_app):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    os.system = m

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit 1')

    # We have an editor, so should expect a system call
    m.assert_called_once()


def test_edit_blank(base_app):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the os.system call so we don't actually open an editor
    m = mock.MagicMock(name='system')
    os.system = m

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')

    run_cmd(base_app, 'edit')

    # We have an editor, so should expect a system call
    m.assert_called_once()


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
    app.intro = 'Hello World, this is an intro ...'
    app.cmdqueue.append('quit\n')
    app.stdout = StdOut()

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    expected = app.intro + '\n'
    with mock.patch.object(sys, 'argv', testargs):
        # Run the command loop
        app.cmdloop()
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
    app.intro = 'Hello World, this is an intro ...'
    app.stdout = StdOut()

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='quit')
    sm.input = m

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    expected = app.intro + '\n{}'.format(app.prompt)
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

def test_default_to_shell_found(shell_app):
    out = run_cmd(shell_app, 'ls -hal')
    assert out == []

def test_default_to_shell_unknown(shell_app):
    unknown_command = 'zyxcw23'
    out = run_cmd(shell_app, unknown_command)
    assert out == ["*** Unknown syntax: {}".format(unknown_command)]


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
