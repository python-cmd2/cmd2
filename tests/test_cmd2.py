"""Cmd2 unit/functional testing"""

import builtins
import io
import os
import signal
import sys
import tempfile
from code import (
    InteractiveConsole,
)
from typing import NoReturn
from unittest import mock

import pytest
from rich.text import Text

import cmd2
from cmd2 import (
    COMMAND_NAME,
    Cmd2Style,
    Color,
    RichPrintKwargs,
    clipboard,
    constants,
    exceptions,
    plugin,
    stylize,
    utils,
)
from cmd2 import rich_utils as ru
from cmd2 import string_utils as su

# This ensures gnureadline is used in macOS tests
from cmd2.rl_utils import readline  # type: ignore[atrr-defined]

from .conftest import (
    SHORTCUTS_TXT,
    complete_tester,
    normalize,
    odd_file_names,
    run_cmd,
    verify_help_text,
    with_ansi_style,
)


def create_outsim_app():
    c = cmd2.Cmd()
    c.stdout = utils.StdSim(c.stdout)
    return c


@pytest.fixture
def outsim_app():
    return create_outsim_app()


def test_version(base_app) -> None:
    assert cmd2.__version__


def test_not_in_main_thread(base_app, capsys) -> None:
    import threading

    # Mock threading.main_thread() to return our fake thread
    saved_main_thread = threading.main_thread
    fake_main = threading.Thread()
    threading.main_thread = mock.MagicMock(name='main_thread', return_value=fake_main)

    with pytest.raises(RuntimeError) as excinfo:
        base_app.cmdloop()

    # Restore threading.main_thread()
    threading.main_thread = saved_main_thread
    assert "cmdloop must be run in the main thread" in str(excinfo.value)


def test_empty_statement(base_app) -> None:
    out, _err = run_cmd(base_app, '')
    expected = normalize('')
    assert out == expected


def test_base_help(base_app) -> None:
    out, _err = run_cmd(base_app, 'help')
    assert base_app.last_result is True
    verify_help_text(base_app, out)


def test_base_help_verbose(base_app) -> None:
    out, _err = run_cmd(base_app, 'help -v')
    assert base_app.last_result is True
    verify_help_text(base_app, out)

    # Make sure :param type lines are filtered out of help summary
    help_doc = base_app.do_help.__func__.__doc__
    help_doc += "\n:param fake param"
    base_app.do_help.__func__.__doc__ = help_doc

    out, _err = run_cmd(base_app, 'help --verbose')
    assert base_app.last_result is True
    verify_help_text(base_app, out)
    assert ':param' not in ''.join(out)


def test_base_argparse_help(base_app) -> None:
    # Verify that "set -h" gives the same output as "help set" and that it starts in a way that makes sense
    out1, _err1 = run_cmd(base_app, 'set -h')
    out2, _err2 = run_cmd(base_app, 'help set')

    assert out1 == out2
    assert out1[0].startswith('Usage: set')
    assert out1[1] == ''
    assert out1[2].startswith('Set a settable parameter')


def test_base_invalid_option(base_app) -> None:
    _out, err = run_cmd(base_app, 'set -z')
    assert err[0] == 'Usage: set [-h] [param] [value]'
    assert 'Error: unrecognized arguments: -z' in err[1]


def test_base_shortcuts(base_app) -> None:
    out, _err = run_cmd(base_app, 'shortcuts')
    expected = normalize(SHORTCUTS_TXT)
    assert out == expected
    assert base_app.last_result is True


def test_command_starts_with_shortcut() -> None:
    expected_err = "Invalid command name 'help'"
    with pytest.raises(ValueError, match=expected_err):
        cmd2.Cmd(shortcuts={'help': 'fake'})


def test_base_set(base_app) -> None:
    # Make sure all settables appear in output.
    out, _err = run_cmd(base_app, 'set')
    settables = sorted(base_app.settables.keys())

    # The settables will appear in order in the table.
    # Go line-by-line until all settables are found.
    for line in out:
        if not settables:
            break
        if line.lstrip().startswith(settables[0]):
            settables.pop(0)

    # This will be empty if we found all settables in the output.
    assert not settables

    # Make sure all settables appear in last_result.
    assert len(base_app.last_result) == len(base_app.settables)
    for param in base_app.last_result:
        assert base_app.last_result[param] == base_app.settables[param].value


def test_set(base_app) -> None:
    out, _err = run_cmd(base_app, 'set quiet True')
    expected = normalize(
        """
quiet - was: False
now: True
"""
    )
    assert out == expected
    assert base_app.last_result is True

    line_found = False
    out, _err = run_cmd(base_app, 'set quiet')
    for line in out:
        if "quiet" in line and "True" in line and "False" not in line:
            line_found = True
            break

    assert line_found
    assert len(base_app.last_result) == 1
    assert base_app.last_result['quiet'] is True


def test_set_val_empty(base_app) -> None:
    base_app.editor = "fake"
    _out, _err = run_cmd(base_app, 'set editor ""')
    assert base_app.editor == ''
    assert base_app.last_result is True


def test_set_val_is_flag(base_app) -> None:
    base_app.editor = "fake"
    _out, _err = run_cmd(base_app, 'set editor "-h"')
    assert base_app.editor == '-h'
    assert base_app.last_result is True


def test_set_not_supported(base_app) -> None:
    _out, err = run_cmd(base_app, 'set qqq True')
    expected = normalize(
        """
Parameter 'qqq' not supported (type 'set' for list of parameters).
"""
    )
    assert err == expected
    assert base_app.last_result is False


def test_set_no_settables(base_app) -> None:
    base_app._settables.clear()
    _out, err = run_cmd(base_app, 'set quiet True')
    expected = normalize("There are no settable parameters")
    assert err == expected
    assert base_app.last_result is False


@pytest.mark.parametrize(
    ('new_val', 'is_valid', 'expected'),
    [
        (ru.AllowStyle.NEVER, True, ru.AllowStyle.NEVER),
        ('neVeR', True, ru.AllowStyle.NEVER),
        (ru.AllowStyle.TERMINAL, True, ru.AllowStyle.TERMINAL),
        ('TeRMInal', True, ru.AllowStyle.TERMINAL),
        (ru.AllowStyle.ALWAYS, True, ru.AllowStyle.ALWAYS),
        ('AlWaYs', True, ru.AllowStyle.ALWAYS),
        ('invalid', False, ru.AllowStyle.TERMINAL),
    ],
)
@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_set_allow_style(base_app, new_val, is_valid, expected) -> None:
    # Use the set command to alter allow_style
    out, err = run_cmd(base_app, f'set allow_style {new_val}')
    assert base_app.last_result is is_valid

    # Verify the results
    assert expected == ru.ALLOW_STYLE
    if is_valid:
        assert not err
        assert out


def test_set_with_choices(base_app) -> None:
    """Test choices validation of Settables"""
    fake_choices = ['valid', 'choices']
    base_app.fake = fake_choices[0]

    fake_settable = cmd2.Settable('fake', type(base_app.fake), "fake description", base_app, choices=fake_choices)
    base_app.add_settable(fake_settable)

    # Try a valid choice
    _out, err = run_cmd(base_app, f'set fake {fake_choices[1]}')
    assert base_app.last_result is True
    assert not err

    # Try an invalid choice
    _out, err = run_cmd(base_app, 'set fake bad_value')
    assert base_app.last_result is False
    assert err[0].startswith("Error setting fake: invalid choice")


class OnChangeHookApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_settable(utils.Settable('quiet', bool, "my description", self, onchange_cb=self._onchange_quiet))

    def _onchange_quiet(self, name, old, new) -> None:
        """Runs when quiet is changed via set command"""
        self.poutput("You changed " + name)


@pytest.fixture
def onchange_app():
    return OnChangeHookApp()


def test_set_onchange_hook(onchange_app) -> None:
    out, _err = run_cmd(onchange_app, 'set quiet True')
    expected = normalize(
        """
You changed quiet
quiet - was: False
now: True
"""
    )
    assert out == expected
    assert onchange_app.last_result is True


def test_base_shell(base_app, monkeypatch) -> None:
    m = mock.Mock()
    monkeypatch.setattr("{}.Popen".format('subprocess'), m)
    out, _err = run_cmd(base_app, 'shell echo a')
    assert out == []
    assert m.called


def test_shell_last_result(base_app) -> None:
    base_app.last_result = None
    run_cmd(base_app, 'shell fake')
    assert base_app.last_result is not None


def test_shell_manual_call(base_app) -> None:
    # Verifies crash from Issue #986 doesn't happen
    cmds = ['echo "hi"', 'echo "there"', 'echo "cmd2!"']
    cmd = ';'.join(cmds)

    base_app.do_shell(cmd)

    cmd = '&&'.join(cmds)

    base_app.do_shell(cmd)


def test_base_error(base_app) -> None:
    _out, err = run_cmd(base_app, 'meow')
    assert "is not a recognized command" in err[0]


def test_base_error_suggest_command(base_app) -> None:
    try:
        old_suggest_similar_command = base_app.suggest_similar_command
        base_app.suggest_similar_command = True
        _out, err = run_cmd(base_app, 'historic')
        assert "history" in err[1]
    finally:
        base_app.suggest_similar_command = old_suggest_similar_command


def test_run_script(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Get output out the script
    script_out, script_err = run_cmd(base_app, f'run_script {filename}')
    assert base_app.last_result is True

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


def test_run_script_with_empty_args(base_app) -> None:
    _out, err = run_cmd(base_app, 'run_script')
    assert "the following arguments are required" in err[1]
    assert base_app.last_result is None


def test_run_script_with_invalid_file(base_app, request) -> None:
    # Path does not exist
    _out, err = run_cmd(base_app, 'run_script does_not_exist.txt')
    assert "Problem accessing script from " in err[0]
    assert base_app.last_result is False

    # Path is a directory
    test_dir = os.path.dirname(request.module.__file__)
    _out, err = run_cmd(base_app, f'run_script {test_dir}')
    assert "Problem accessing script from " in err[0]
    assert base_app.last_result is False


def test_run_script_with_empty_file(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'empty.txt')
    out, err = run_cmd(base_app, f'run_script {filename}')
    assert not out
    assert not err
    assert base_app.last_result is True


def test_run_script_with_binary_file(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'binary.bin')
    _out, err = run_cmd(base_app, f'run_script {filename}')
    assert "is not an ASCII or UTF-8 encoded text file" in err[0]
    assert base_app.last_result is False


def test_run_script_with_python_file(base_app, request) -> None:
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'pyscript', 'stop.py')
    _out, err = run_cmd(base_app, f'run_script {filename}')
    assert "appears to be a Python file" in err[0]
    assert base_app.last_result is False


def test_run_script_with_utf8_file(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'utf8.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Get output out the script
    script_out, script_err = run_cmd(base_app, f'run_script {filename}')
    assert base_app.last_result is True

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


def test_scripts_add_to_history(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'help.txt')
    command = f'run_script {filename}'

    # Add to history
    base_app.scripts_add_to_history = True
    base_app.history.clear()
    run_cmd(base_app, command)
    assert len(base_app.history) == 2
    assert base_app.history.get(1).raw == command
    assert base_app.history.get(2).raw == 'help -v'

    # Do not add to history
    base_app.scripts_add_to_history = False
    base_app.history.clear()
    run_cmd(base_app, command)
    assert len(base_app.history) == 1
    assert base_app.history.get(1).raw == command


def test_run_script_nested_run_scripts(base_app, request) -> None:
    # Verify that running a script with nested run_script commands works correctly,
    # and runs the nested script commands in the correct order.
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'nested.txt')

    # Run the top level script
    initial_run = 'run_script ' + filename
    run_cmd(base_app, initial_run)
    assert base_app.last_result is True

    # Check that the right commands were executed.
    expected = f"""
{initial_run}
_relative_run_script precmds.txt
set allow_style Always
help
shortcuts
_relative_run_script postcmds.txt
set allow_style Never"""
    out, _err = run_cmd(base_app, 'history -s')
    assert out == normalize(expected)


def test_runcmds_plus_hooks(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    prefilepath = os.path.join(test_dir, 'scripts', 'precmds.txt')
    postfilepath = os.path.join(test_dir, 'scripts', 'postcmds.txt')

    base_app.runcmds_plus_hooks(['run_script ' + prefilepath, 'help', 'shortcuts', 'run_script ' + postfilepath])
    expected = f"""
run_script {prefilepath}
set allow_style Always
help
shortcuts
run_script {postfilepath}
set allow_style Never"""

    out, _err = run_cmd(base_app, 'history -s')
    assert out == normalize(expected)


def test_runcmds_plus_hooks_ctrl_c(base_app, capsys) -> None:
    """Test Ctrl-C while in runcmds_plus_hooks"""
    import types

    def do_keyboard_interrupt(self, _) -> NoReturn:
        raise KeyboardInterrupt('Interrupting this command')

    base_app.do_keyboard_interrupt = types.MethodType(do_keyboard_interrupt, base_app)

    # Default behavior is to not stop runcmds_plus_hooks() on Ctrl-C
    base_app.history.clear()
    base_app.runcmds_plus_hooks(['help', 'keyboard_interrupt', 'shortcuts'])
    _out, err = capsys.readouterr()
    assert not err
    assert len(base_app.history) == 3

    # Ctrl-C should stop runcmds_plus_hooks() in this case
    base_app.history.clear()
    base_app.runcmds_plus_hooks(['help', 'keyboard_interrupt', 'shortcuts'], stop_on_keyboard_interrupt=True)
    _out, err = capsys.readouterr()
    assert err.startswith("Interrupting this command")
    assert len(base_app.history) == 2


def test_relative_run_script(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # Get output out the script
    script_out, script_err = run_cmd(base_app, f'_relative_run_script {filename}')
    assert base_app.last_result is True

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


@pytest.mark.parametrize('file_name', odd_file_names)
def test_relative_run_script_with_odd_file_names(base_app, file_name, monkeypatch) -> None:
    """Test file names with various patterns"""
    # Mock out the do_run_script call to see what args are passed to it
    run_script_mock = mock.MagicMock(name='do_run_script')
    monkeypatch.setattr("cmd2.Cmd.do_run_script", run_script_mock)

    run_cmd(base_app, f"_relative_run_script {su.quote(file_name)}")
    run_script_mock.assert_called_once_with(su.quote(file_name))


def test_relative_run_script_requires_an_argument(base_app) -> None:
    _out, err = run_cmd(base_app, '_relative_run_script')
    assert 'Error: the following arguments' in err[1]
    assert base_app.last_result is None


def test_in_script(request) -> None:
    class HookApp(cmd2.Cmd):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.register_cmdfinalization_hook(self.hook)

        def hook(self: cmd2.Cmd, data: plugin.CommandFinalizationData) -> plugin.CommandFinalizationData:
            if self.in_script():
                self.poutput("WE ARE IN SCRIPT")
            return data

    hook_app = HookApp()
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')
    out, _err = run_cmd(hook_app, f'run_script {filename}')

    assert "WE ARE IN SCRIPT" in out[-1]


def test_system_exit_in_command(base_app, capsys) -> None:
    """Test raising SystemExit in a command"""
    import types

    exit_code = 5

    def do_system_exit(self, _) -> NoReturn:
        raise SystemExit(exit_code)

    base_app.do_system_exit = types.MethodType(do_system_exit, base_app)

    stop = base_app.onecmd_plus_hooks('system_exit')
    assert stop
    assert base_app.exit_code == exit_code


def test_passthrough_exception_in_command(base_app) -> None:
    """Test raising a PassThroughException in a command"""
    import types

    expected_err = "Pass me up"

    def do_passthrough(self, _) -> NoReturn:
        wrapped_ex = OSError(expected_err)
        raise exceptions.PassThroughException(wrapped_ex=wrapped_ex)

    base_app.do_passthrough = types.MethodType(do_passthrough, base_app)

    with pytest.raises(OSError, match=expected_err):
        base_app.onecmd_plus_hooks('passthrough')


class RedirectionApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def do_print_output(self, _: str) -> None:
        """Print output to sys.stdout and self.stdout.."""
        print("print")
        self.poutput("poutput")

    def do_print_feedback(self, _: str) -> None:
        """Call pfeedback."""
        self.pfeedback("feedback")


@pytest.fixture
def redirection_app():
    return RedirectionApp()


def test_output_redirection(redirection_app) -> None:
    fd, filename = tempfile.mkstemp(prefix='cmd2_test', suffix='.txt')
    os.close(fd)

    try:
        # Verify that writing to a file works
        run_cmd(redirection_app, f'print_output > {filename}')
        with open(filename) as f:
            lines = f.read().splitlines()
        assert lines[0] == "print"
        assert lines[1] == "poutput"

        # Verify that appending to a file also works
        run_cmd(redirection_app, f'print_output >> {filename}')
        with open(filename) as f:
            lines = f.read().splitlines()
        assert lines[0] == "print"
        assert lines[1] == "poutput"
        assert lines[2] == "print"
        assert lines[3] == "poutput"
    finally:
        os.remove(filename)


def test_output_redirection_custom_stdout(redirection_app) -> None:
    """sys.stdout should not redirect if it's different than self.stdout."""
    fd, filename = tempfile.mkstemp(prefix='cmd2_test', suffix='.txt')
    os.close(fd)

    redirection_app.stdout = io.StringIO()
    try:
        # Verify that we only see output written to self.stdout
        run_cmd(redirection_app, f'print_output > {filename}')
        with open(filename) as f:
            lines = f.read().splitlines()
        assert "print" not in lines
        assert lines[0] == "poutput"

        # Verify that appending to a file also works
        run_cmd(redirection_app, f'print_output >> {filename}')
        with open(filename) as f:
            lines = f.read().splitlines()
        assert "print" not in lines
        assert lines[0] == "poutput"
        assert lines[1] == "poutput"
    finally:
        os.remove(filename)


def test_output_redirection_to_nonexistent_directory(redirection_app) -> None:
    filename = '~/fakedir/this_does_not_exist.txt'

    _out, err = run_cmd(redirection_app, f'print_output > {filename}')
    assert 'Failed to redirect' in err[0]

    _out, err = run_cmd(redirection_app, f'print_output >> {filename}')
    assert 'Failed to redirect' in err[0]


def test_output_redirection_to_too_long_filename(redirection_app) -> None:
    filename = (
        '~/sdkfhksdjfhkjdshfkjsdhfkjsdhfkjdshfkjdshfkjshdfkhdsfkjhewfuihewiufhweiufhiweufhiuewhiuewhfiuwehfia'
        'ewhfiuewhfiuewhfiuewhiuewhfiuewhfiuewfhiuwehewiufhewiuhfiweuhfiuwehfiuewfhiuwehiuewfhiuewhiewuhfiueh'
        'fiuwefhewiuhewiufhewiufhewiufhewiufhewiufhewiufhewiufhewiuhewiufhewiufhewiuheiufhiuewheiwufhewiufheu'
        'fheiufhieuwhfewiuhfeiufhiuewfhiuewheiwuhfiuewhfiuewhfeiuwfhewiufhiuewhiuewhfeiuwhfiuwehfuiwehfiuehie'
        'whfieuwfhieufhiuewhfeiuwfhiuefhueiwhfw'
    )

    _out, err = run_cmd(redirection_app, f'print_output > {filename}')
    assert 'Failed to redirect' in err[0]

    _out, err = run_cmd(redirection_app, f'print_output >> {filename}')
    assert 'Failed to redirect' in err[0]


def test_feedback_to_output_true(redirection_app) -> None:
    redirection_app.feedback_to_output = True
    f, filename = tempfile.mkstemp(prefix='cmd2_test', suffix='.txt')
    os.close(f)

    try:
        run_cmd(redirection_app, f'print_feedback > {filename}')
        with open(filename) as f:
            content = f.read().splitlines()
        assert "feedback" in content
    finally:
        os.remove(filename)


def test_feedback_to_output_false(redirection_app) -> None:
    redirection_app.feedback_to_output = False
    f, filename = tempfile.mkstemp(prefix='feedback_to_output', suffix='.txt')
    os.close(f)

    try:
        _out, err = run_cmd(redirection_app, f'print_feedback > {filename}')

        with open(filename) as f:
            content = f.read().splitlines()
        assert not content
        assert "feedback" in err
    finally:
        os.remove(filename)


def test_disallow_redirection(redirection_app) -> None:
    # Set allow_redirection to False
    redirection_app.allow_redirection = False

    filename = 'test_allow_redirect.txt'

    # Verify output wasn't redirected
    out, _err = run_cmd(redirection_app, f'print_output > {filename}')
    assert "print" in out
    assert "poutput" in out

    # Verify that no file got created
    assert not os.path.exists(filename)


def test_pipe_to_shell(redirection_app) -> None:
    out, err = run_cmd(redirection_app, "print_output | sort")
    assert "print" in out
    assert "poutput" in out
    assert not err


def test_pipe_to_shell_custom_stdout(redirection_app) -> None:
    """sys.stdout should not redirect if it's different than self.stdout."""
    redirection_app.stdout = io.StringIO()
    out, err = run_cmd(redirection_app, "print_output | sort")
    assert "print" not in out
    assert "poutput" in out
    assert not err


def test_pipe_to_shell_and_redirect(redirection_app) -> None:
    filename = 'out.txt'
    out, err = run_cmd(redirection_app, f"print_output | sort > {filename}")
    assert not out
    assert not err
    assert os.path.exists(filename)
    os.remove(filename)


def test_pipe_to_shell_error(redirection_app) -> None:
    # Try to pipe command output to a shell command that doesn't exist in order to produce an error
    out, err = run_cmd(redirection_app, 'print_output | foobarbaz.this_does_not_exist')
    assert not out
    assert "Pipe process exited with code" in err[0]


try:
    # try getting the contents of the clipboard
    _ = clipboard.get_paste_buffer()
    # pyperclip raises at least the following types of exceptions
    #   FileNotFoundError on Windows Subsystem for Linux (WSL) when Windows paths are removed from $PATH
    #   ValueError for headless Linux systems without Gtk installed
    #   AssertionError can be raised by paste_klipper().
    #   PyperclipException for pyperclip-specific exceptions
except Exception:  # noqa: BLE001
    can_paste = False
else:
    can_paste = True


@pytest.mark.skipif(not can_paste, reason="Pyperclip could not find a copy/paste mechanism for your system")
def test_send_to_paste_buffer(redirection_app) -> None:
    # Test writing to the PasteBuffer/Clipboard
    run_cmd(redirection_app, 'print_output >')
    lines = cmd2.cmd2.get_paste_buffer().splitlines()
    assert lines[0] == "print"
    assert lines[1] == "poutput"

    # Test appending to the PasteBuffer/Clipboard
    run_cmd(redirection_app, 'print_output >>')
    lines = cmd2.cmd2.get_paste_buffer().splitlines()
    assert lines[0] == "print"
    assert lines[1] == "poutput"
    assert lines[2] == "print"
    assert lines[3] == "poutput"


@pytest.mark.skipif(not can_paste, reason="Pyperclip could not find a copy/paste mechanism for your system")
def test_send_to_paste_buffer_custom_stdout(redirection_app) -> None:
    """sys.stdout should not redirect if it's different than self.stdout."""
    redirection_app.stdout = io.StringIO()

    # Verify that we only see output written to self.stdout
    run_cmd(redirection_app, 'print_output >')
    lines = cmd2.cmd2.get_paste_buffer().splitlines()
    assert "print" not in lines
    assert lines[0] == "poutput"

    # Test appending to the PasteBuffer/Clipboard
    run_cmd(redirection_app, 'print_output >>')
    lines = cmd2.cmd2.get_paste_buffer().splitlines()
    assert "print" not in lines
    assert lines[0] == "poutput"
    assert lines[1] == "poutput"


def test_get_paste_buffer_exception(redirection_app, mocker, capsys) -> None:
    # Force get_paste_buffer to throw an exception
    pastemock = mocker.patch('pyperclip.paste')
    pastemock.side_effect = ValueError('foo')

    # Redirect command output to the clipboard
    redirection_app.onecmd_plus_hooks('print_output > ')

    # Make sure we got the exception output
    out, err = capsys.readouterr()
    assert out == ''
    # this just checks that cmd2 is surfacing whatever error gets raised by pyperclip.paste
    assert 'ValueError' in err
    assert 'foo' in err


def test_allow_clipboard_initializer(redirection_app) -> None:
    assert redirection_app.allow_clipboard is True
    noclipcmd = cmd2.Cmd(allow_clipboard=False)
    assert noclipcmd.allow_clipboard is False


# if clipboard access is not allowed, cmd2 should check that first
# before it tries to do anything with pyperclip, that's why we can
# safely run this test without skipping it if pyperclip doesn't
# work in the test environment, like we do for test_send_to_paste_buffer()
def test_allow_clipboard(base_app) -> None:
    base_app.allow_clipboard = False
    out, err = run_cmd(base_app, 'help >')
    assert not out
    assert "Clipboard access not allowed" in err


def test_base_timing(base_app) -> None:
    base_app.feedback_to_output = False
    out, err = run_cmd(base_app, 'set timing True')
    expected = normalize(
        """timing - was: False
now: True
"""
    )
    assert out == expected

    if sys.platform == 'win32':
        assert err[0].startswith('Elapsed: 0:00:00')
    else:
        assert err[0].startswith('Elapsed: 0:00:00.0')


def test_base_debug(base_app) -> None:
    # Purposely set the editor to None
    base_app.editor = None

    # Make sure we get an exception, but cmd2 handles it
    out, err = run_cmd(base_app, 'edit')
    assert "ValueError: Please use 'set editor'" in err[0]
    assert "To enable full traceback" in err[3]

    # Set debug true
    out, err = run_cmd(base_app, 'set debug True')
    expected = normalize(
        """
debug - was: False
now: True
"""
    )
    assert out == expected

    # Verify that we now see the exception traceback
    out, err = run_cmd(base_app, 'edit')
    assert 'Traceback (most recent call last)' in err[0]


def test_debug_not_settable(base_app) -> None:
    # Set debug to False and make it unsettable
    base_app.debug = False
    base_app.remove_settable('debug')

    # Cause an exception by setting editor to None and running edit
    base_app.editor = None
    _out, err = run_cmd(base_app, 'edit')

    # Since debug is unsettable, the user will not be given the option to enable a full traceback
    assert err == ["ValueError: Please use 'set editor' to specify your text editing program of", 'choice.']


def test_blank_exception(mocker, base_app):
    mocker.patch("cmd2.Cmd.do_help", side_effect=Exception)
    _out, err = run_cmd(base_app, 'help')

    # When an exception has no message, the first error line is just its type.
    assert err[0] == "Exception"


def test_remove_settable_keyerror(base_app) -> None:
    with pytest.raises(KeyError):
        base_app.remove_settable('fake')


def test_edit_file(base_app, request, monkeypatch) -> None:
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'script.txt')

    run_cmd(base_app, f'edit {filename}')

    # We think we have an editor, so should expect a Popen call
    m.assert_called_once()


@pytest.mark.parametrize('file_name', odd_file_names)
def test_edit_file_with_odd_file_names(base_app, file_name, monkeypatch) -> None:
    """Test editor and file names with various patterns"""
    # Mock out the do_shell call to see what args are passed to it
    shell_mock = mock.MagicMock(name='do_shell')
    monkeypatch.setattr("cmd2.Cmd.do_shell", shell_mock)

    base_app.editor = 'fooedit'
    file_name = su.quote('nothingweird.py')
    run_cmd(base_app, f"edit {su.quote(file_name)}")
    shell_mock.assert_called_once_with(f'"fooedit" {su.quote(file_name)}')


def test_edit_file_with_spaces(base_app, request, monkeypatch) -> None:
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'my commands.txt')

    run_cmd(base_app, f'edit "{filename}"')

    # We think we have an editor, so should expect a Popen call
    m.assert_called_once()


def test_edit_blank(base_app, monkeypatch) -> None:
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    run_cmd(base_app, 'edit')

    # We have an editor, so should expect a Popen call
    m.assert_called_once()


def test_base_py_interactive(base_app) -> None:
    # Mock out the InteractiveConsole.interact() call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='interact')
    InteractiveConsole.interact = m

    run_cmd(base_app, "py")

    # Make sure our mock was called once and only once
    m.assert_called_once()


def test_base_cmdloop_with_startup_commands() -> None:
    intro = 'Hello World, this is an intro ...'

    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog", 'quit']
    expected = intro + '\n'

    with mock.patch.object(sys, 'argv', testargs):
        app = create_outsim_app()

    app.use_rawinput = True

    # Run the command loop with custom intro
    app.cmdloop(intro=intro)

    out = app.stdout.getvalue()
    assert out == expected


def test_base_cmdloop_without_startup_commands() -> None:
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    with mock.patch.object(sys, 'argv', testargs):
        app = create_outsim_app()

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


def test_cmdloop_without_rawinput() -> None:
    # Need to patch sys.argv so cmd2 doesn't think it was called with arguments equal to the py.test args
    testargs = ["prog"]
    with mock.patch.object(sys, 'argv', testargs):
        app = create_outsim_app()

    app.use_rawinput = False
    app.echo = False
    app.intro = 'Hello World, this is an intro ...'

    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input', return_value='quit')
    builtins.input = m

    expected = app.intro + '\n'

    with pytest.raises(OSError):  # noqa: PT011
        app.cmdloop()
    out = app.stdout.getvalue()
    assert out == expected


def test_cmdfinalizations_runs(base_app, monkeypatch) -> None:
    """Make sure _run_cmdfinalization_hooks is run after each command."""
    with (
        mock.patch('sys.stdin.isatty', mock.MagicMock(name='isatty', return_value=True)),
        mock.patch('sys.stdin.fileno', mock.MagicMock(name='fileno', return_value=0)),
    ):
        monkeypatch.setattr(base_app.stdin, "fileno", lambda: 0)
        monkeypatch.setattr(base_app.stdin, "isatty", lambda: True)

        cmd_fin = mock.MagicMock(name='cmdfinalization')
        monkeypatch.setattr("cmd2.Cmd._run_cmdfinalization_hooks", cmd_fin)

        base_app.onecmd_plus_hooks('help')
        cmd_fin.assert_called_once()


@pytest.mark.skipif(sys.platform.startswith('win'), reason="termios is not available on Windows")
@pytest.mark.parametrize(
    ('is_tty', 'settings_set', 'raised_exception', 'should_call'),
    [
        (True, True, None, True),
        (True, True, 'termios_error', True),
        (True, True, 'unsupported_operation', True),
        (False, True, None, False),
        (True, False, None, False),
    ],
)
def test_restore_termios_settings(base_app, monkeypatch, is_tty, settings_set, raised_exception, should_call):
    """Test that terminal settings are restored after a command and that errors are suppressed."""
    import io
    import termios  # Mock termios since it's imported within the method

    termios_mock = mock.MagicMock()
    # The error attribute needs to be the actual exception for isinstance checks
    termios_mock.error = termios.error
    monkeypatch.setitem(sys.modules, 'termios', termios_mock)

    # Set the exception to be raised by tcsetattr
    if raised_exception == 'termios_error':
        termios_mock.tcsetattr.side_effect = termios.error("test termios error")
    elif raised_exception == 'unsupported_operation':
        termios_mock.tcsetattr.side_effect = io.UnsupportedOperation("test io error")

    # Set initial termios settings so the logic will run
    if settings_set:
        termios_settings = ["dummy settings"]
        base_app._initial_termios_settings = termios_settings
    else:
        base_app._initial_termios_settings = None
        termios_settings = None  # for the assert

    # Mock stdin to make it look like a TTY
    monkeypatch.setattr(base_app.stdin, "isatty", lambda: is_tty)
    monkeypatch.setattr(base_app.stdin, "fileno", lambda: 0)

    # Run a command to trigger _run_cmdfinalization_hooks
    # This should not raise an exception
    base_app.onecmd_plus_hooks('help')

    # Verify that tcsetattr was called with the correct arguments
    if should_call:
        termios_mock.tcsetattr.assert_called_once_with(0, termios_mock.TCSANOW, termios_settings)
    else:
        termios_mock.tcsetattr.assert_not_called()


def test_sigint_handler(base_app) -> None:
    # No KeyboardInterrupt should be raised when using sigint_protection
    with base_app.sigint_protection:
        base_app.sigint_handler(signal.SIGINT, 1)

    # Without sigint_protection, a KeyboardInterrupt is raised
    with pytest.raises(KeyboardInterrupt):
        base_app.sigint_handler(signal.SIGINT, 1)


def test_raise_keyboard_interrupt(base_app) -> None:
    with pytest.raises(KeyboardInterrupt) as excinfo:
        base_app._raise_keyboard_interrupt()
    assert 'Got a keyboard interrupt' in str(excinfo.value)


@pytest.mark.skipif(sys.platform.startswith('win'), reason="SIGTERM only handled on Linux/Mac")
def test_termination_signal_handler(base_app) -> None:
    with pytest.raises(SystemExit) as excinfo:
        base_app.termination_signal_handler(signal.SIGHUP, 1)
    assert excinfo.value.code == signal.SIGHUP + 128

    with pytest.raises(SystemExit) as excinfo:
        base_app.termination_signal_handler(signal.SIGTERM, 1)
    assert excinfo.value.code == signal.SIGTERM + 128


class HookFailureApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # register a postparsing hook method
        self.register_postparsing_hook(self.postparsing_precmd)

    def postparsing_precmd(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Simulate precmd hook failure."""
        data.stop = True
        return data


@pytest.fixture
def hook_failure():
    return HookFailureApp()


def test_precmd_hook_success(base_app) -> None:
    out = base_app.onecmd_plus_hooks('help')
    assert out is False


def test_precmd_hook_failure(hook_failure) -> None:
    out = hook_failure.onecmd_plus_hooks('help')
    assert out is True


class SayApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def do_say(self, arg) -> None:
        self.poutput(arg)


@pytest.fixture
def say_app():
    app = SayApp(allow_cli_args=False)
    app.stdout = utils.StdSim(app.stdout)
    return app


def test_ctrl_c_at_prompt(say_app) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    m = mock.MagicMock(name='input')
    m.side_effect = ['say hello', KeyboardInterrupt(), 'say goodbye', 'eof']
    builtins.input = m

    say_app.cmdloop()

    # And verify the expected output to stdout
    out = say_app.stdout.getvalue()
    assert out == 'hello\n^C\ngoodbye\n\n'


class ShellApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.default_to_shell = True


def test_default_to_shell(base_app, monkeypatch) -> None:
    if sys.platform.startswith('win'):
        line = 'dir'
    else:
        line = 'ls'

    base_app.default_to_shell = True
    m = mock.Mock()
    monkeypatch.setattr("{}.Popen".format('subprocess'), m)
    out, _err = run_cmd(base_app, line)
    assert out == []
    assert m.called


def test_escaping_prompt() -> None:
    from cmd2.rl_utils import (
        rl_escape_prompt,
        rl_unescape_prompt,
    )

    # This prompt has nothing which needs to be escaped
    prompt = '(Cmd) '
    assert rl_escape_prompt(prompt) == prompt

    # This prompt has color which needs to be escaped
    prompt = stylize('InColor', style=Color.CYAN)

    escape_start = "\x01"
    escape_end = "\x02"

    escaped_prompt = rl_escape_prompt(prompt)
    if sys.platform.startswith('win'):
        # PyReadline on Windows doesn't need to escape invisible characters
        assert escaped_prompt == prompt
    else:
        cyan = "\x1b[36m"
        reset_all = "\x1b[0m"
        assert escaped_prompt.startswith(escape_start + cyan + escape_end)
        assert escaped_prompt.endswith(escape_start + reset_all + escape_end)

    assert rl_unescape_prompt(escaped_prompt) == prompt


class HelpApp(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.doc_leader = "I now present you with a list of help topics."
        self.doc_header = "My very custom doc header."
        self.misc_header = "Various topics found here."
        self.undoc_header = "Why did no one document these?"

    def do_squat(self, arg) -> None:
        """This docstring help will never be shown because the help_squat method overrides it."""

    def help_squat(self) -> None:
        self.stdout.write('This command does diddly squat...\n')

    def do_edit(self, arg) -> None:
        """This overrides the edit command and does nothing."""

    # This command will be in the "undocumented" section of the help menu
    def do_undoc(self, arg) -> None:
        pass

    def do_multiline_docstr(self, arg) -> None:
        """This documentation
        is multiple lines
        and there are no
        tabs
        """

    def help_physics(self):
        """A miscellaneous help topic."""
        self.poutput("Here is some help on physics.")

    parser_cmd_parser = cmd2.Cmd2ArgumentParser(description="This is the description.")

    @cmd2.with_argparser(parser_cmd_parser)
    def do_parser_cmd(self, args) -> None:
        """This is the docstring."""


@pytest.fixture
def help_app():
    return HelpApp()


def test_help_headers(capsys) -> None:
    help_app = HelpApp()
    help_app.onecmd_plus_hooks('help')
    out, _err = capsys.readouterr()

    assert help_app.doc_leader in out
    assert help_app.doc_header in out
    assert help_app.misc_header in out
    assert help_app.undoc_header in out
    assert help_app.last_result is True


def test_custom_command_help(help_app) -> None:
    out, _err = run_cmd(help_app, 'help squat')
    expected = normalize('This command does diddly squat...')
    assert out == expected
    assert help_app.last_result is True


def test_custom_help_menu(help_app) -> None:
    out, _err = run_cmd(help_app, 'help')
    verify_help_text(help_app, out)
    assert help_app.last_result is True


def test_help_undocumented(help_app) -> None:
    _out, err = run_cmd(help_app, 'help undoc')
    assert err[0].startswith("No help on undoc")
    assert help_app.last_result is False


def test_help_overridden_method(help_app) -> None:
    out, _err = run_cmd(help_app, 'help edit')
    expected = normalize('This overrides the edit command and does nothing.')
    assert out == expected
    assert help_app.last_result is True


def test_help_multiline_docstring(help_app) -> None:
    out, _err = run_cmd(help_app, 'help multiline_docstr')
    expected = normalize('This documentation\nis multiple lines\nand there are no\ntabs')
    assert out == expected
    assert help_app.last_result is True


def test_miscellaneous_help_topic(help_app) -> None:
    out, _err = run_cmd(help_app, 'help physics')
    expected = normalize("Here is some help on physics.")
    assert out == expected
    assert help_app.last_result is True


def test_help_verbose_uses_parser_description(help_app: HelpApp) -> None:
    out, _err = run_cmd(help_app, 'help --verbose')
    expected_verbose = utils.strip_doc_annotations(help_app.do_parser_cmd.__doc__)
    verify_help_text(help_app, out, verbose_strings=[expected_verbose])


def test_help_verbose_with_fake_command(capsys) -> None:
    """Verify that only actual command functions appear in verbose output."""
    help_app = HelpApp()

    cmds = ["alias", "fake_command"]
    help_app._print_documented_command_topics(help_app.doc_header, cmds, verbose=True)
    out, _err = capsys.readouterr()
    assert cmds[0] in out
    assert cmds[1] not in out


def test_render_columns_no_strs(help_app: HelpApp) -> None:
    no_strs = []
    result = help_app.render_columns(no_strs)
    assert result == ""


def test_render_columns_one_str(help_app: HelpApp) -> None:
    one_str = ["one_string"]
    result = help_app.render_columns(one_str)
    assert result == "one_string"


def test_render_columns_too_wide(help_app: HelpApp) -> None:
    commands = ["kind_of_long_string", "a_slightly_longer_string"]
    result = help_app.render_columns(commands, display_width=10)

    expected = "kind_of_long_string     \na_slightly_longer_string"
    assert result == expected


def test_columnize(capsys: pytest.CaptureFixture[str]) -> None:
    help_app = HelpApp()
    items = ["one", "two"]
    help_app.columnize(items)
    out, _err = capsys.readouterr()

    # poutput() adds a newline at the end.
    expected = "one  two\n"
    assert out == expected


class HelpCategoriesApp(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""

    SOME_CATEGORY = "Some Category"
    CUSTOM_CATEGORY = "Custom Category"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @cmd2.with_category('Some Category')
    def do_diddly(self, arg) -> None:
        """This command does diddly"""

    # This command will be in the "Some Category" section of the help menu even though it has no docstring
    @cmd2.with_category(SOME_CATEGORY)
    def do_cat_nodoc(self, arg) -> None:
        pass

    # This command will show in the category labeled with self.default_category
    def do_squat(self, arg) -> None:
        """This docstring help will never be shown because the help_squat method overrides it."""

    def help_squat(self) -> None:
        self.stdout.write('This command does diddly squat...\n')

    def do_edit(self, arg) -> None:
        """This overrides the edit command and does nothing."""

    cmd2.categorize((do_squat, do_edit), CUSTOM_CATEGORY)

    # This command will be in the "undocumented" section of the help menu
    def do_undoc(self, arg) -> None:
        pass


@pytest.fixture
def helpcat_app():
    return HelpCategoriesApp()


def test_help_cat_base(helpcat_app) -> None:
    out, _err = run_cmd(helpcat_app, 'help')
    assert helpcat_app.last_result is True
    verify_help_text(helpcat_app, out)

    help_text = ''.join(out)
    assert helpcat_app.CUSTOM_CATEGORY in help_text
    assert helpcat_app.SOME_CATEGORY in help_text
    assert helpcat_app.default_category in help_text


def test_help_cat_verbose(helpcat_app) -> None:
    out, _err = run_cmd(helpcat_app, 'help --verbose')
    assert helpcat_app.last_result is True
    verify_help_text(helpcat_app, out)

    help_text = ''.join(out)
    assert helpcat_app.CUSTOM_CATEGORY in help_text
    assert helpcat_app.SOME_CATEGORY in help_text
    assert helpcat_app.default_category in help_text


class SelectApp(cmd2.Cmd):
    def do_eat(self, arg) -> None:
        """Eat something, with a selection of sauces to choose from."""
        # Pass in a single string of space-separated selections
        sauce = self.select('sweet salty', 'Sauce? ')
        result = '{food} with {sauce} sauce, yum!'
        result = result.format(food=arg, sauce=sauce)
        self.stdout.write(result + '\n')

    def do_study(self, arg) -> None:
        """Learn something, with a selection of subjects to choose from."""
        # Pass in a list of strings for selections
        subject = self.select(['math', 'science'], 'Subject? ')
        result = f'Good luck learning {subject}!\n'
        self.stdout.write(result)

    def do_procrastinate(self, arg) -> None:
        """Waste time in your manner of choice."""
        # Pass in a list of tuples for selections
        leisure_activity = self.select(
            [('Netflix and chill', 'Netflix'), ('YouTube', 'WebSurfing')], 'How would you like to procrastinate? '
        )
        result = f'Have fun procrasinating with {leisure_activity}!\n'
        self.stdout.write(result)

    def do_play(self, arg) -> None:
        """Play your favorite musical instrument."""
        # Pass in an uneven list of tuples for selections
        instrument = self.select([('Guitar', 'Electric Guitar'), ('Drums',)], 'Instrument? ')
        result = f'Charm us with the {instrument}...\n'
        self.stdout.write(result)

    def do_return_type(self, arg) -> None:
        """Test that return values can be non-strings"""
        choice = self.select([(1, 'Integer'), ("test_str", 'String'), (self.do_play, 'Method')], 'Choice? ')
        result = f'The return type is {type(choice)}\n'
        self.stdout.write(result)


@pytest.fixture
def select_app():
    return SelectApp()


def test_select_options(select_app, monkeypatch) -> None:
    # Mock out the read_input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input', return_value='2')
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    food = 'bacon'
    out, _err = run_cmd(select_app, f"eat {food}")
    expected = normalize(
        f"""
   1. sweet
   2. salty
{food} with salty sauce, yum!
"""
    )

    # Make sure our mock was called with the expected arguments
    read_input_mock.assert_called_once_with('Sauce? ')

    # And verify the expected output to stdout
    assert out == expected


def test_select_invalid_option_too_big(select_app, monkeypatch) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input')

    # If side_effect is an iterable then each call to the mock will return the next value from the iterable.
    read_input_mock.side_effect = ['3', '1']  # First pass an invalid selection, then pass a valid one
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    food = 'fish'
    out, _err = run_cmd(select_app, f"eat {food}")
    expected = normalize(
        f"""
   1. sweet
   2. salty
'3' isn't a valid choice. Pick a number between 1 and 2:
{food} with sweet sauce, yum!
"""
    )

    # Make sure our mock was called exactly twice with the expected arguments
    arg = 'Sauce? '
    calls = [mock.call(arg), mock.call(arg)]
    read_input_mock.assert_has_calls(calls)
    assert read_input_mock.call_count == 2

    # And verify the expected output to stdout
    assert out == expected


def test_select_invalid_option_too_small(select_app, monkeypatch) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input')

    # If side_effect is an iterable then each call to the mock will return the next value from the iterable.
    read_input_mock.side_effect = ['0', '1']  # First pass an invalid selection, then pass a valid one
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    food = 'fish'
    out, _err = run_cmd(select_app, f"eat {food}")
    expected = normalize(
        f"""
   1. sweet
   2. salty
'0' isn't a valid choice. Pick a number between 1 and 2:
{food} with sweet sauce, yum!
"""
    )

    # Make sure our mock was called exactly twice with the expected arguments
    arg = 'Sauce? '
    calls = [mock.call(arg), mock.call(arg)]
    read_input_mock.assert_has_calls(calls)
    assert read_input_mock.call_count == 2

    # And verify the expected output to stdout
    assert out == expected


def test_select_list_of_strings(select_app, monkeypatch) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input', return_value='2')
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    out, _err = run_cmd(select_app, "study")
    expected = normalize(
        """
   1. math
   2. science
Good luck learning {}!
""".format('science')
    )

    # Make sure our mock was called with the expected arguments
    read_input_mock.assert_called_once_with('Subject? ')

    # And verify the expected output to stdout
    assert out == expected


def test_select_list_of_tuples(select_app, monkeypatch) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input', return_value='2')
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    out, _err = run_cmd(select_app, "procrastinate")
    expected = normalize(
        """
   1. Netflix
   2. WebSurfing
Have fun procrasinating with {}!
""".format('YouTube')
    )

    # Make sure our mock was called with the expected arguments
    read_input_mock.assert_called_once_with('How would you like to procrastinate? ')

    # And verify the expected output to stdout
    assert out == expected


def test_select_uneven_list_of_tuples(select_app, monkeypatch) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input', return_value='2')
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    out, _err = run_cmd(select_app, "play")
    expected = normalize(
        """
   1. Electric Guitar
   2. Drums
Charm us with the {}...
""".format('Drums')
    )

    # Make sure our mock was called with the expected arguments
    read_input_mock.assert_called_once_with('Instrument? ')

    # And verify the expected output to stdout
    assert out == expected


@pytest.mark.parametrize(
    ('selection', 'type_str'),
    [
        ('1', "<class 'int'>"),
        ('2', "<class 'str'>"),
        ('3', "<class 'method'>"),
    ],
)
def test_select_return_type(select_app, monkeypatch, selection, type_str) -> None:
    # Mock out the input call so we don't actually wait for a user's response on stdin
    read_input_mock = mock.MagicMock(name='read_input', return_value=selection)
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    out, _err = run_cmd(select_app, "return_type")
    expected = normalize(
        f"""
   1. Integer
   2. String
   3. Method
The return type is {type_str}
"""
    )

    # Make sure our mock was called with the expected arguments
    read_input_mock.assert_called_once_with('Choice? ')

    # And verify the expected output to stdout
    assert out == expected


def test_select_eof(select_app, monkeypatch) -> None:
    # Ctrl-D during select causes an EOFError that just reprompts the user
    read_input_mock = mock.MagicMock(name='read_input', side_effect=[EOFError, 2])
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    food = 'fish'
    _out, _err = run_cmd(select_app, f"eat {food}")

    # Make sure our mock was called exactly twice with the expected arguments
    arg = 'Sauce? '
    calls = [mock.call(arg), mock.call(arg)]
    read_input_mock.assert_has_calls(calls)
    assert read_input_mock.call_count == 2


def test_select_ctrl_c(outsim_app, monkeypatch) -> None:
    # Ctrl-C during select prints ^C and raises a KeyboardInterrupt
    read_input_mock = mock.MagicMock(name='read_input', side_effect=KeyboardInterrupt)
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    with pytest.raises(KeyboardInterrupt):
        outsim_app.select([('Guitar', 'Electric Guitar'), ('Drums',)], 'Instrument? ')

    out = outsim_app.stdout.getvalue()
    assert out.rstrip().endswith('^C')


class HelpNoDocstringApp(cmd2.Cmd):
    greet_parser = cmd2.Cmd2ArgumentParser()
    greet_parser.add_argument('-s', '--shout', action="store_true", help="N00B EMULATION MODE")

    @cmd2.with_argparser(greet_parser, with_unknown_args=True)
    def do_greet(self, opts, arg) -> None:
        arg = ''.join(arg)
        if opts.shout:
            arg = arg.upper()
        self.stdout.write(arg + '\n')


def test_help_with_no_docstring(capsys) -> None:
    app = HelpNoDocstringApp()
    app.onecmd_plus_hooks('greet -h')
    out, err = capsys.readouterr()
    assert err == ''
    assert (
        out
        == """Usage: greet [-h] [-s]

Optional Arguments:
  -h, --help   show this help message and exit
  -s, --shout  N00B EMULATION MODE

"""
    )


class MultilineApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, multiline_commands=['orate'], **kwargs)

    orate_parser = cmd2.Cmd2ArgumentParser()
    orate_parser.add_argument('-s', '--shout', action="store_true", help="N00B EMULATION MODE")

    @cmd2.with_argparser(orate_parser, with_unknown_args=True)
    def do_orate(self, opts, arg) -> None:
        arg = ''.join(arg)
        if opts.shout:
            arg = arg.upper()
        self.stdout.write(arg + '\n')


@pytest.fixture
def multiline_app():
    return MultilineApp()


def test_multiline_complete_empty_statement_raises_exception(multiline_app) -> None:
    with pytest.raises(exceptions.EmptyStatement):
        multiline_app._complete_statement('')


def test_multiline_complete_statement_without_terminator(multiline_app) -> None:
    # Mock out the input call so we don't actually wait for a user's response
    # on stdin when it looks for more input
    m = mock.MagicMock(name='input', return_value='\n')
    builtins.input = m

    command = 'orate'
    args = 'hello world'
    line = f'{command} {args}'
    statement = multiline_app._complete_statement(line)
    assert statement == args
    assert statement.command == command
    assert statement.multiline_command == command


def test_multiline_complete_statement_with_unclosed_quotes(multiline_app) -> None:
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


def test_multiline_input_line_to_statement(multiline_app) -> None:
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


def test_multiline_history_no_prior_history(multiline_app) -> None:
    # Test no existing history prior to typing the command
    m = mock.MagicMock(name='input', side_effect=['person', '\n'])
    builtins.input = m

    # Set orig_rl_history_length to 0 before the first line is typed.
    readline.clear_history()
    orig_rl_history_length = readline.get_current_history_length()

    line = "orate hi"
    readline.add_history(line)
    multiline_app._complete_statement(line, orig_rl_history_length=orig_rl_history_length)

    assert readline.get_current_history_length() == orig_rl_history_length + 1
    assert readline.get_history_item(1) == "orate hi person"


def test_multiline_history_first_line_matches_prev_entry(multiline_app) -> None:
    # Test when first line of multiline command matches previous history entry
    m = mock.MagicMock(name='input', side_effect=['person', '\n'])
    builtins.input = m

    # Since the first line of our command matches the previous entry,
    # orig_rl_history_length is set before the first line is typed.
    line = "orate hi"
    readline.clear_history()
    readline.add_history(line)
    orig_rl_history_length = readline.get_current_history_length()

    multiline_app._complete_statement(line, orig_rl_history_length=orig_rl_history_length)

    assert readline.get_current_history_length() == orig_rl_history_length + 1
    assert readline.get_history_item(1) == line
    assert readline.get_history_item(2) == "orate hi person"


def test_multiline_history_matches_prev_entry(multiline_app) -> None:
    # Test combined multiline command that matches previous history entry
    m = mock.MagicMock(name='input', side_effect=['person', '\n'])
    builtins.input = m

    readline.clear_history()
    readline.add_history("orate hi person")
    orig_rl_history_length = readline.get_current_history_length()

    line = "orate hi"
    readline.add_history(line)
    multiline_app._complete_statement(line, orig_rl_history_length=orig_rl_history_length)

    # Since it matches the previous history item, nothing was added to readline history
    assert readline.get_current_history_length() == orig_rl_history_length
    assert readline.get_history_item(1) == "orate hi person"


def test_multiline_history_does_not_match_prev_entry(multiline_app) -> None:
    # Test combined multiline command that does not match previous history entry
    m = mock.MagicMock(name='input', side_effect=['person', '\n'])
    builtins.input = m

    readline.clear_history()
    readline.add_history("no match")
    orig_rl_history_length = readline.get_current_history_length()

    line = "orate hi"
    readline.add_history(line)
    multiline_app._complete_statement(line, orig_rl_history_length=orig_rl_history_length)

    # Since it doesn't match the previous history item, it was added to readline history
    assert readline.get_current_history_length() == orig_rl_history_length + 1
    assert readline.get_history_item(1) == "no match"
    assert readline.get_history_item(2) == "orate hi person"


def test_multiline_history_with_quotes(multiline_app) -> None:
    # Test combined multiline command with quotes
    m = mock.MagicMock(name='input', side_effect=['  and spaces  ', ' "', ' in', 'quotes.', ';'])
    builtins.input = m

    readline.clear_history()
    orig_rl_history_length = readline.get_current_history_length()

    line = 'orate Look, "There are newlines'
    readline.add_history(line)
    multiline_app._complete_statement(line, orig_rl_history_length=orig_rl_history_length)

    # Since spaces and newlines in quotes are preserved, this history entry spans multiple lines.
    assert readline.get_current_history_length() == orig_rl_history_length + 1

    history_lines = readline.get_history_item(1).splitlines()
    assert history_lines[0] == 'orate Look, "There are newlines'
    assert history_lines[1] == '  and spaces  '
    assert history_lines[2] == ' " in quotes.;'


class CommandResultApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def do_affirmative(self, arg) -> None:
        self.last_result = cmd2.CommandResult(arg, data=True)

    def do_negative(self, arg) -> None:
        self.last_result = cmd2.CommandResult(arg, data=False)

    def do_affirmative_no_data(self, arg) -> None:
        self.last_result = cmd2.CommandResult(arg)

    def do_negative_no_data(self, arg) -> None:
        self.last_result = cmd2.CommandResult('', arg)


@pytest.fixture
def commandresult_app():
    return CommandResultApp()


def test_commandresult_truthy(commandresult_app) -> None:
    arg = 'foo'
    run_cmd(commandresult_app, f'affirmative {arg}')
    assert commandresult_app.last_result
    assert commandresult_app.last_result == cmd2.CommandResult(arg, data=True)

    run_cmd(commandresult_app, f'affirmative_no_data {arg}')
    assert commandresult_app.last_result
    assert commandresult_app.last_result == cmd2.CommandResult(arg)


def test_commandresult_falsy(commandresult_app) -> None:
    arg = 'bar'
    run_cmd(commandresult_app, f'negative {arg}')
    assert not commandresult_app.last_result
    assert commandresult_app.last_result == cmd2.CommandResult(arg, data=False)

    run_cmd(commandresult_app, f'negative_no_data {arg}')
    assert not commandresult_app.last_result
    assert commandresult_app.last_result == cmd2.CommandResult('', arg)


@pytest.mark.skipif(sys.platform.startswith('win'), reason="Test is problematic on GitHub Actions Windows runners")
def test_is_text_file_bad_input(base_app) -> None:
    # Test with a non-existent file
    with pytest.raises(FileNotFoundError):
        utils.is_text_file('does_not_exist.txt')

    # Test with a directory
    with pytest.raises(IsADirectoryError):
        utils.is_text_file('.')


def test_eof(base_app) -> None:
    # Only thing to verify is that it returns True
    assert base_app.do_eof('')
    assert base_app.last_result is True


def test_quit(base_app) -> None:
    # Only thing to verify is that it returns True
    assert base_app.do_quit('')
    assert base_app.last_result is True


def test_echo(capsys) -> None:
    app = cmd2.Cmd()
    app.echo = True
    commands = ['help history']

    app.runcmds_plus_hooks(commands)

    out, _err = capsys.readouterr()
    assert out.startswith(f'{app.prompt}{commands[0]}\nUsage: history')


def test_read_input_rawinput_true(capsys, monkeypatch) -> None:
    prompt_str = 'the_prompt'
    input_str = 'some input'

    app = cmd2.Cmd()
    app.use_rawinput = True

    # Mock out input() to return input_str
    monkeypatch.setattr("builtins.input", lambda *args: input_str)

    # isatty is True
    with mock.patch('sys.stdin.isatty', mock.MagicMock(name='isatty', return_value=True)):
        line = app.read_input(prompt_str)
        assert line == input_str

        # Run custom history code
        readline.add_history('old_history')
        custom_history = ['cmd1', 'cmd2']
        line = app.read_input(prompt_str, history=custom_history, completion_mode=cmd2.CompletionMode.NONE)
        assert line == input_str
        readline.clear_history()

        # Run all completion modes
        line = app.read_input(prompt_str, completion_mode=cmd2.CompletionMode.NONE)
        assert line == input_str

        line = app.read_input(prompt_str, completion_mode=cmd2.CompletionMode.COMMANDS)
        assert line == input_str

        # custom choices
        custom_choices = ['choice1', 'choice2']
        line = app.read_input(prompt_str, completion_mode=cmd2.CompletionMode.CUSTOM, choices=custom_choices)
        assert line == input_str

        # custom choices_provider
        line = app.read_input(
            prompt_str, completion_mode=cmd2.CompletionMode.CUSTOM, choices_provider=cmd2.Cmd.get_all_commands
        )
        assert line == input_str

        # custom completer
        line = app.read_input(prompt_str, completion_mode=cmd2.CompletionMode.CUSTOM, completer=cmd2.Cmd.path_complete)
        assert line == input_str

        # custom parser
        line = app.read_input(prompt_str, completion_mode=cmd2.CompletionMode.CUSTOM, parser=cmd2.Cmd2ArgumentParser())
        assert line == input_str

    # isatty is False
    with mock.patch('sys.stdin.isatty', mock.MagicMock(name='isatty', return_value=False)):
        # echo True
        app.echo = True
        line = app.read_input(prompt_str)
        out, _err = capsys.readouterr()
        assert line == input_str
        assert out == f"{prompt_str}{input_str}\n"

        # echo False
        app.echo = False
        line = app.read_input(prompt_str)
        out, _err = capsys.readouterr()
        assert line == input_str
        assert not out


def test_read_input_rawinput_false(capsys, monkeypatch) -> None:
    prompt_str = 'the_prompt'
    input_str = 'some input'

    def make_app(isatty: bool, empty_input: bool = False):
        """Make a cmd2 app with a custom stdin"""
        app_input_str = '' if empty_input else input_str

        fakein = io.StringIO(f'{app_input_str}')
        fakein.isatty = mock.MagicMock(name='isatty', return_value=isatty)

        new_app = cmd2.Cmd(stdin=fakein)
        new_app.use_rawinput = False
        return new_app

    # isatty True
    app = make_app(isatty=True)
    line = app.read_input(prompt_str)
    out, _err = capsys.readouterr()
    assert line == input_str
    assert out == prompt_str

    # isatty True, empty input
    app = make_app(isatty=True, empty_input=True)
    line = app.read_input(prompt_str)
    out, _err = capsys.readouterr()
    assert line == 'eof'
    assert out == prompt_str

    # isatty is False, echo is True
    app = make_app(isatty=False)
    app.echo = True
    line = app.read_input(prompt_str)
    out, _err = capsys.readouterr()
    assert line == input_str
    assert out == f"{prompt_str}{input_str}\n"

    # isatty is False, echo is False
    app = make_app(isatty=False)
    app.echo = False
    line = app.read_input(prompt_str)
    out, _err = capsys.readouterr()
    assert line == input_str
    assert not out

    # isatty is False, empty input
    app = make_app(isatty=False, empty_input=True)
    line = app.read_input(prompt_str)
    out, _err = capsys.readouterr()
    assert line == 'eof'
    assert not out


def test_custom_stdout() -> None:
    # Create a custom file-like object (e.g., an in-memory string buffer)
    custom_output = io.StringIO()

    # Instantiate cmd2.Cmd with the custom_output as stdout
    my_app = cmd2.Cmd(stdout=custom_output)

    # Simulate a command
    my_app.onecmd('help')

    # Retrieve the output from the custom_output buffer
    captured_output = custom_output.getvalue()
    assert 'history' in captured_output


def test_read_command_line_eof(base_app, monkeypatch) -> None:
    read_input_mock = mock.MagicMock(name='read_input', side_effect=EOFError)
    monkeypatch.setattr("cmd2.Cmd.read_input", read_input_mock)

    line = base_app._read_command_line("Prompt> ")
    assert line == 'eof'


def test_poutput_string(outsim_app) -> None:
    msg = 'This is a test'
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = msg + '\n'
    assert out == expected


def test_poutput_zero(outsim_app) -> None:
    msg = 0
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = str(msg) + '\n'
    assert out == expected


def test_poutput_empty_string(outsim_app) -> None:
    msg = ''
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = '\n'
    assert out == expected


def test_poutput_none(outsim_app) -> None:
    msg = None
    outsim_app.poutput(msg)
    out = outsim_app.stdout.getvalue()
    expected = 'None\n'
    assert out == expected


@with_ansi_style(ru.AllowStyle.ALWAYS)
@pytest.mark.parametrize(
    # Test a Rich Text and a string.
    ('styled_msg', 'expected'),
    [
        (Text("A Text object", style="cyan"), "\x1b[36mA Text object\x1b[0m\n"),
        (su.stylize("A str object", style="blue"), "\x1b[34mA str object\x1b[0m\n"),
    ],
)
def test_poutput_ansi_always(styled_msg, expected, outsim_app) -> None:
    outsim_app.poutput(styled_msg)
    out = outsim_app.stdout.getvalue()
    assert out == expected


@with_ansi_style(ru.AllowStyle.NEVER)
@pytest.mark.parametrize(
    # Test a Rich Text and a string.
    ('styled_msg', 'expected'),
    [
        (Text("A Text object", style="cyan"), "A Text object\n"),
        (su.stylize("A str object", style="blue"), "A str object\n"),
    ],
)
def test_poutput_ansi_never(styled_msg, expected, outsim_app) -> None:
    outsim_app.poutput(styled_msg)
    out = outsim_app.stdout.getvalue()
    assert out == expected


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_poutput_ansi_terminal(outsim_app) -> None:
    """Test that AllowStyle.TERMINAL strips style when redirecting."""
    msg = 'testing...'
    colored_msg = Text(msg, style="cyan")
    outsim_app._redirecting = True
    outsim_app.poutput(colored_msg)
    out = outsim_app.stdout.getvalue()
    expected = msg + '\n'
    assert out == expected


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_highlight(outsim_app):
    outsim_app.poutput("My IP Address is 192.168.1.100.", highlight=True)
    out = outsim_app.stdout.getvalue()
    assert out == "My IP Address is \x1b[1;92m192.168.1.100\x1b[0m.\n"


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_markup(outsim_app):
    outsim_app.poutput("The leaves are [green]green[/green].", markup=True)
    out = outsim_app.stdout.getvalue()
    assert out == "The leaves are \x1b[32mgreen\x1b[0m.\n"


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_emoji(outsim_app):
    outsim_app.poutput("Look at the emoji :1234:.", emoji=True)
    out = outsim_app.stdout.getvalue()
    assert out == "Look at the emoji 🔢.\n"


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_justify_and_width(outsim_app):
    rich_print_kwargs = RichPrintKwargs(justify="right", width=10)

    # Use a styled-string when justifying to check if its display width is correct.
    outsim_app.poutput(
        su.stylize("Hello", style="blue"),
        rich_print_kwargs=rich_print_kwargs,
    )
    out = outsim_app.stdout.getvalue()
    assert out == "     \x1b[34mHello\x1b[0m\n"


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_no_wrap_and_overflow(outsim_app):
    rich_print_kwargs = RichPrintKwargs(no_wrap=True, overflow="ellipsis", width=10)

    outsim_app.poutput(
        "This is longer than width.",
        soft_wrap=False,
        rich_print_kwargs=rich_print_kwargs,
    )
    out = outsim_app.stdout.getvalue()
    assert out.startswith("This is l…\n")


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_pretty_print(outsim_app):
    """Test that cmd2 passes objects through so they can be pretty-printed when highlighting is enabled."""
    dictionary = {1: 'hello', 2: 'person', 3: 'who', 4: 'codes'}

    outsim_app.poutput(dictionary, highlight=True)
    out = outsim_app.stdout.getvalue()
    assert out.startswith("\x1b[1m{\x1b[0m\x1b[1;36m1\x1b[0m: \x1b[32m'hello'\x1b[0m")


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_poutput_all_keyword_args(outsim_app):
    """Test that all fields in RichPrintKwargs are recognized by Rich's Console.print()."""
    rich_print_kwargs = RichPrintKwargs(
        justify="center",
        overflow="ellipsis",
        no_wrap=True,
        width=40,
        height=50,
        crop=False,
        new_line_start=True,
    )

    outsim_app.poutput(
        "My string",
        rich_print_kwargs=rich_print_kwargs,
    )

    # Verify that something printed which means Console.print() didn't
    # raise a TypeError for an unexpected keyword argument.
    out = outsim_app.stdout.getvalue()
    assert "My string" in out


def test_broken_pipe_error(outsim_app, monkeypatch, capsys):
    write_mock = mock.MagicMock()
    write_mock.side_effect = BrokenPipeError
    monkeypatch.setattr("cmd2.utils.StdSim.write", write_mock)

    outsim_app.broken_pipe_warning = "The pipe broke"
    outsim_app.poutput("My test string")

    out, err = capsys.readouterr()
    assert not out
    assert outsim_app.broken_pipe_warning in err


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


def test_get_alias_completion_items(base_app) -> None:
    run_cmd(base_app, 'alias create fake run_pyscript')
    run_cmd(base_app, 'alias create ls !ls -hal')

    results = base_app._get_alias_completion_items()
    assert len(results) == len(base_app.aliases)

    for cur_res in results:
        assert cur_res in base_app.aliases
        # Strip trailing spaces from table output
        assert cur_res.descriptive_data[0].rstrip() == base_app.aliases[cur_res]


def test_get_macro_completion_items(base_app) -> None:
    run_cmd(base_app, 'macro create foo !echo foo')
    run_cmd(base_app, 'macro create bar !echo bar')

    results = base_app._get_macro_completion_items()
    assert len(results) == len(base_app.macros)

    for cur_res in results:
        assert cur_res in base_app.macros
        # Strip trailing spaces from table output
        assert cur_res.descriptive_data[0].rstrip() == base_app.macros[cur_res].value


def test_get_settable_completion_items(base_app) -> None:
    results = base_app._get_settable_completion_items()
    assert len(results) == len(base_app.settables)

    for cur_res in results:
        cur_settable = base_app.settables.get(cur_res)
        assert cur_settable is not None

        # These CompletionItem descriptions are a two column table (Settable Value and Settable Description)
        # First check if the description text starts with the value
        str_value = str(cur_settable.value)
        assert cur_res.descriptive_data[0].startswith(str_value)

        # The second column is likely to have wrapped long text. So we will just examine the
        # first couple characters to look for the Settable's description.
        assert cur_settable.description[0:10] in cur_res.descriptive_data[1]


def test_alias_no_subcommand(base_app) -> None:
    _out, err = run_cmd(base_app, 'alias')
    assert "Usage: alias [-h]" in err[0]
    assert "Error: the following arguments are required: SUBCOMMAND" in err[1]


def test_alias_create(base_app) -> None:
    # Create the alias
    out, err = run_cmd(base_app, 'alias create fake run_pyscript')
    assert out == normalize("Alias 'fake' created")
    assert base_app.last_result is True

    # Use the alias
    out, err = run_cmd(base_app, 'fake')
    assert "the following arguments are required: script_path" in err[1]

    # See a list of aliases
    out, err = run_cmd(base_app, 'alias list')
    assert out == normalize('alias create fake run_pyscript')
    assert len(base_app.last_result) == len(base_app.aliases)
    assert base_app.last_result['fake'] == "run_pyscript"

    # Look up the new alias
    out, err = run_cmd(base_app, 'alias list fake')
    assert out == normalize('alias create fake run_pyscript')
    assert len(base_app.last_result) == 1
    assert base_app.last_result['fake'] == "run_pyscript"

    # Overwrite alias
    out, err = run_cmd(base_app, 'alias create fake help')
    assert out == normalize("Alias 'fake' overwritten")
    assert base_app.last_result is True

    # Look up the updated alias
    out, err = run_cmd(base_app, 'alias list fake')
    assert out == normalize('alias create fake help')
    assert len(base_app.last_result) == 1
    assert base_app.last_result['fake'] == "help"


def test_alias_create_with_quoted_tokens(base_app) -> None:
    """Demonstrate that quotes in alias value will be preserved"""
    alias_name = "fake"
    alias_command = 'help ">" "out file.txt" ";"'
    create_command = f"alias create {alias_name} {alias_command}"

    # Create the alias
    out, _err = run_cmd(base_app, create_command)
    assert out == normalize("Alias 'fake' created")

    # Look up the new alias and verify all quotes are preserved
    out, _err = run_cmd(base_app, 'alias list fake')
    assert out == normalize(create_command)
    assert len(base_app.last_result) == 1
    assert base_app.last_result[alias_name] == alias_command


@pytest.mark.parametrize('alias_name', invalid_command_name)
def test_alias_create_invalid_name(base_app, alias_name, capsys) -> None:
    _out, err = run_cmd(base_app, f'alias create {alias_name} help')
    assert "Invalid alias name" in err[0]
    assert base_app.last_result is False


def test_alias_create_with_command_name(base_app) -> None:
    _out, err = run_cmd(base_app, 'alias create help stuff')
    assert "Alias cannot have the same name as a command" in err[0]
    assert base_app.last_result is False


def test_alias_create_with_macro_name(base_app) -> None:
    macro = "my_macro"
    run_cmd(base_app, f'macro create {macro} help')
    _out, err = run_cmd(base_app, f'alias create {macro} help')
    assert "Alias cannot have the same name as a macro" in err[0]
    assert base_app.last_result is False


def test_alias_that_resolves_into_comment(base_app) -> None:
    # Create the alias
    out, err = run_cmd(base_app, 'alias create fake ' + constants.COMMENT_CHAR + ' blah blah')
    assert out == normalize("Alias 'fake' created")

    # Use the alias
    out, err = run_cmd(base_app, 'fake')
    assert not out
    assert not err


def test_alias_list_invalid_alias(base_app) -> None:
    # Look up invalid alias
    _out, err = run_cmd(base_app, 'alias list invalid')
    assert "Alias 'invalid' not found" in err[0]
    assert base_app.last_result == {}


def test_alias_delete(base_app) -> None:
    # Create an alias
    run_cmd(base_app, 'alias create fake run_pyscript')

    # Delete the alias
    out, _err = run_cmd(base_app, 'alias delete fake')
    assert out == normalize("Alias 'fake' deleted")
    assert base_app.last_result is True


def test_alias_delete_all(base_app) -> None:
    out, _err = run_cmd(base_app, 'alias delete --all')
    assert out == normalize("All aliases deleted")
    assert base_app.last_result is True


def test_alias_delete_non_existing(base_app) -> None:
    _out, err = run_cmd(base_app, 'alias delete fake')
    assert "Alias 'fake' does not exist" in err[0]
    assert base_app.last_result is True


def test_alias_delete_no_name(base_app) -> None:
    _out, err = run_cmd(base_app, 'alias delete')
    assert "Either --all or alias name(s)" in err[0]
    assert base_app.last_result is False


def test_multiple_aliases(base_app) -> None:
    alias1 = 'h1'
    alias2 = 'h2'
    run_cmd(base_app, f'alias create {alias1} help')
    run_cmd(base_app, f'alias create {alias2} help -v')
    out, _err = run_cmd(base_app, alias1)
    verify_help_text(base_app, out)

    out, _err = run_cmd(base_app, alias2)
    verify_help_text(base_app, out)


def test_macro_no_subcommand(base_app) -> None:
    _out, err = run_cmd(base_app, 'macro')
    assert "Usage: macro [-h]" in err[0]
    assert "Error: the following arguments are required: SUBCOMMAND" in err[1]


def test_macro_create(base_app) -> None:
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake run_pyscript')
    assert out == normalize("Macro 'fake' created")
    assert base_app.last_result is True

    # Use the macro
    out, err = run_cmd(base_app, 'fake')
    assert "the following arguments are required: script_path" in err[1]

    # See a list of macros
    out, err = run_cmd(base_app, 'macro list')
    assert out == normalize('macro create fake run_pyscript')
    assert len(base_app.last_result) == len(base_app.macros)
    assert base_app.last_result['fake'] == "run_pyscript"

    # Look up the new macro
    out, err = run_cmd(base_app, 'macro list fake')
    assert out == normalize('macro create fake run_pyscript')
    assert len(base_app.last_result) == 1
    assert base_app.last_result['fake'] == "run_pyscript"

    # Overwrite macro
    out, err = run_cmd(base_app, 'macro create fake help')
    assert out == normalize("Macro 'fake' overwritten")
    assert base_app.last_result is True

    # Look up the updated macro
    out, err = run_cmd(base_app, 'macro list fake')
    assert out == normalize('macro create fake help')
    assert len(base_app.last_result) == 1
    assert base_app.last_result['fake'] == "help"


def test_macro_create_with_quoted_tokens(base_app) -> None:
    """Demonstrate that quotes in macro value will be preserved"""
    macro_name = "fake"
    macro_command = 'help ">" "out file.txt" ";"'
    create_command = f"macro create {macro_name} {macro_command}"

    # Create the macro
    out, _err = run_cmd(base_app, create_command)
    assert out == normalize("Macro 'fake' created")

    # Look up the new macro and verify all quotes are preserved
    out, _err = run_cmd(base_app, 'macro list fake')
    assert out == normalize(create_command)
    assert len(base_app.last_result) == 1
    assert base_app.last_result[macro_name] == macro_command


@pytest.mark.parametrize('macro_name', invalid_command_name)
def test_macro_create_invalid_name(base_app, macro_name) -> None:
    _out, err = run_cmd(base_app, f'macro create {macro_name} help')
    assert "Invalid macro name" in err[0]
    assert base_app.last_result is False


def test_macro_create_with_command_name(base_app) -> None:
    _out, err = run_cmd(base_app, 'macro create help stuff')
    assert "Macro cannot have the same name as a command" in err[0]
    assert base_app.last_result is False


def test_macro_create_with_alias_name(base_app) -> None:
    macro = "my_macro"
    run_cmd(base_app, f'alias create {macro} help')
    _out, err = run_cmd(base_app, f'macro create {macro} help')
    assert "Macro cannot have the same name as an alias" in err[0]
    assert base_app.last_result is False


def test_macro_create_with_args(base_app) -> None:
    # Create the macro
    out, _err = run_cmd(base_app, 'macro create fake {1} {2}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, _err = run_cmd(base_app, 'fake help -v')
    verify_help_text(base_app, out)


def test_macro_create_with_escaped_args(base_app) -> None:
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {{1}}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake')
    assert err[0].startswith('No help on {1}')


def test_macro_usage_with_missing_args(base_app) -> None:
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake help {1} {2}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake arg1')
    assert "expects at least 2 arguments" in err[0]


def test_macro_usage_with_exta_args(base_app) -> None:
    # Create the macro
    out, _err = run_cmd(base_app, 'macro create fake help {1}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, _err = run_cmd(base_app, 'fake alias create')
    assert "Usage: alias create" in out[0]


def test_macro_create_with_missing_arg_nums(base_app) -> None:
    # Create the macro
    _out, err = run_cmd(base_app, 'macro create fake help {1} {3}')
    assert "Not all numbers between 1 and 3" in err[0]
    assert base_app.last_result is False


def test_macro_create_with_invalid_arg_num(base_app) -> None:
    # Create the macro
    _out, err = run_cmd(base_app, 'macro create fake help {1} {-1} {0}')
    assert "Argument numbers must be greater than 0" in err[0]
    assert base_app.last_result is False


def test_macro_create_with_unicode_numbered_arg(base_app) -> None:
    # Create the macro expecting 1 argument
    out, err = run_cmd(base_app, 'macro create fake help {\N{ARABIC-INDIC DIGIT ONE}}')
    assert out == normalize("Macro 'fake' created")

    # Run the macro
    out, err = run_cmd(base_app, 'fake')
    assert "expects at least 1 argument" in err[0]


def test_macro_create_with_missing_unicode_arg_nums(base_app) -> None:
    _out, err = run_cmd(base_app, 'macro create fake help {1} {\N{ARABIC-INDIC DIGIT THREE}}')
    assert "Not all numbers between 1 and 3" in err[0]
    assert base_app.last_result is False


def test_macro_that_resolves_into_comment(base_app) -> None:
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake {1} blah blah')
    assert out == normalize("Macro 'fake' created")

    # Use the macro
    out, err = run_cmd(base_app, 'fake ' + constants.COMMENT_CHAR)
    assert not out
    assert not err


def test_macro_list_invalid_macro(base_app) -> None:
    # Look up invalid macro
    _out, err = run_cmd(base_app, 'macro list invalid')
    assert "Macro 'invalid' not found" in err[0]
    assert base_app.last_result == {}


def test_macro_delete(base_app) -> None:
    # Create an macro
    run_cmd(base_app, 'macro create fake run_pyscript')

    # Delete the macro
    out, _err = run_cmd(base_app, 'macro delete fake')
    assert out == normalize("Macro 'fake' deleted")
    assert base_app.last_result is True


def test_macro_delete_all(base_app) -> None:
    out, _err = run_cmd(base_app, 'macro delete --all')
    assert out == normalize("All macros deleted")
    assert base_app.last_result is True


def test_macro_delete_non_existing(base_app) -> None:
    _out, err = run_cmd(base_app, 'macro delete fake')
    assert "Macro 'fake' does not exist" in err[0]
    assert base_app.last_result is True


def test_macro_delete_no_name(base_app) -> None:
    _out, err = run_cmd(base_app, 'macro delete')
    assert "Either --all or macro name(s)" in err[0]
    assert base_app.last_result is False


def test_multiple_macros(base_app) -> None:
    macro1 = 'h1'
    macro2 = 'h2'
    run_cmd(base_app, f'macro create {macro1} help')
    run_cmd(base_app, f'macro create {macro2} help -v')
    out, _err = run_cmd(base_app, macro1)
    verify_help_text(base_app, out)

    out2, _err2 = run_cmd(base_app, macro2)
    verify_help_text(base_app, out2)
    assert len(out2) > len(out)


def test_nonexistent_macro(base_app) -> None:
    from cmd2.parsing import (
        StatementParser,
    )

    exception = None

    try:
        base_app._resolve_macro(StatementParser().parse('fake'))
    except KeyError as e:
        exception = e

    assert exception is not None


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_perror_style(base_app, capsys) -> None:
    msg = 'testing...'
    base_app.perror(msg)
    _out, err = capsys.readouterr()
    assert err == "\x1b[91mtesting...\x1b[0m\n"


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_perror_no_style(base_app, capsys) -> None:
    msg = 'testing...'
    end = '\n'
    base_app.perror(msg, style=None)
    _out, err = capsys.readouterr()
    assert err == msg + end


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_pexcept_style(base_app, capsys) -> None:
    msg = Exception('testing...')

    base_app.pexcept(msg)
    _out, err = capsys.readouterr()
    expected = su.stylize("Exception: ", style="traceback.exc_type")
    assert err.startswith(expected)


@with_ansi_style(ru.AllowStyle.NEVER)
def test_pexcept_no_style(base_app, capsys) -> None:
    msg = Exception('testing...')

    base_app.pexcept(msg)
    _out, err = capsys.readouterr()
    assert err.startswith("Exception: testing...")


@pytest.mark.parametrize('chop', [True, False])
def test_ppaged_with_pager(outsim_app, monkeypatch, chop) -> None:
    """Force ppaged() to run the pager by mocking an actual terminal state."""

    # Make it look like we're in a terminal
    stdin_mock = mock.MagicMock()
    stdin_mock.isatty.return_value = True
    monkeypatch.setattr(outsim_app, "stdin", stdin_mock)

    stdout_mock = mock.MagicMock()
    stdout_mock.isatty.return_value = True
    monkeypatch.setattr(outsim_app, "stdout", stdout_mock)

    if not sys.platform.startswith('win') and os.environ.get("TERM") is None:
        monkeypatch.setenv('TERM', 'simulated')

    # This will force ppaged to call Popen to run a pager
    popen_mock = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", popen_mock)
    outsim_app.ppaged("Test", chop=chop)

    # Verify the correct pager was run
    expected_cmd = outsim_app.pager_chop if chop else outsim_app.pager
    assert len(popen_mock.call_args_list) == 1
    assert expected_cmd == popen_mock.call_args_list[0].args[0]


def test_ppaged_no_pager(outsim_app) -> None:
    """Since we're not in a fully-functional terminal, ppaged() will just call poutput()."""
    msg = 'testing...'
    end = '\n'
    outsim_app.ppaged(msg)
    out = outsim_app.stdout.getvalue()
    assert out == msg + end


# we override cmd.parseline() so we always get consistent
# command parsing by parent methods we don't override
# don't need to test all the parsing logic here, because
# parseline just calls StatementParser.parse_command_only()
def test_parseline_empty(base_app) -> None:
    statement = ''
    command, args, line = base_app.parseline(statement)
    assert not command
    assert not args
    assert not line


def test_parseline_quoted(base_app) -> None:
    statement = " command with 'partially completed quotes  "
    command, args, line = base_app.parseline(statement)
    assert command == 'command'
    assert args == "with 'partially completed quotes  "
    assert line == statement.lstrip()


def test_onecmd_raw_str_continue(outsim_app) -> None:
    line = "help"
    stop = outsim_app.onecmd(line)
    out = outsim_app.stdout.getvalue()
    assert not stop
    verify_help_text(outsim_app, out)


def test_onecmd_raw_str_quit(outsim_app) -> None:
    line = "quit"
    stop = outsim_app.onecmd(line)
    out = outsim_app.stdout.getvalue()
    assert stop
    assert out == ''


def test_onecmd_add_to_history(outsim_app) -> None:
    line = "help"
    saved_hist_len = len(outsim_app.history)

    # Allow command to be added to history
    outsim_app.onecmd(line, add_to_history=True)
    new_hist_len = len(outsim_app.history)
    assert new_hist_len == saved_hist_len + 1

    saved_hist_len = new_hist_len

    # Prevent command from being added to history
    outsim_app.onecmd(line, add_to_history=False)
    new_hist_len = len(outsim_app.history)
    assert new_hist_len == saved_hist_len


def test_get_all_commands(base_app) -> None:
    # Verify that the base app has the expected commands
    commands = base_app.get_all_commands()
    expected_commands = [
        '_relative_run_script',
        'alias',
        'edit',
        'eof',
        'help',
        'history',
        'ipy',
        'macro',
        'py',
        'quit',
        'run_pyscript',
        'run_script',
        'set',
        'shell',
        'shortcuts',
    ]
    assert commands == expected_commands


def test_get_help_topics(base_app) -> None:
    # Verify that the base app has no additional help_foo methods
    custom_help = base_app.get_help_topics()
    assert len(custom_help) == 0


def test_get_help_topics_hidden() -> None:
    # Verify get_help_topics() filters out hidden commands
    class TestApp(cmd2.Cmd):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)

        def do_my_cmd(self, args) -> None:
            pass

        def help_my_cmd(self, args) -> None:
            pass

    app = TestApp()
    assert 'my_cmd' in app.get_help_topics()

    app.hidden_commands.append('my_cmd')
    assert 'my_cmd' not in app.get_help_topics()


class ReplWithExitCode(cmd2.Cmd):
    """Example cmd2 application where we can specify an exit code when existing."""

    def __init__(self) -> None:
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
                self.perror(f"{arg_list[0]} isn't a valid integer exit code")
                self.exit_code = 1

        # Return True to stop the command loop
        return True

    def postloop(self) -> None:
        """Hook method executed once when the cmdloop() method is about to return."""
        self.poutput(f'exiting with code: {self.exit_code}')


@pytest.fixture
def exit_code_repl():
    app = ReplWithExitCode()
    app.stdout = utils.StdSim(app.stdout)
    return app


def test_exit_code_default(exit_code_repl) -> None:
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


def test_exit_code_nonzero(exit_code_repl) -> None:
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


class AnsiApp(cmd2.Cmd):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def do_echo(self, args) -> None:
        self.poutput(args)
        self.perror(args)

    def do_echo_error(self, args) -> None:
        self.poutput(args, style=Cmd2Style.ERROR)
        # perror uses colors by default
        self.perror(args)


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_ansi_pouterr_always_tty(mocker, capsys) -> None:
    app = AnsiApp()
    mocker.patch.object(app.stdout, 'isatty', return_value=True)
    mocker.patch.object(sys.stderr, 'isatty', return_value=True)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    # if colors are on, the output should have some ANSI style sequences in it
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


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_ansi_pouterr_always_notty(mocker, capsys) -> None:
    app = AnsiApp()
    mocker.patch.object(app.stdout, 'isatty', return_value=False)
    mocker.patch.object(sys.stderr, 'isatty', return_value=False)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    # if colors are on, the output should have some ANSI style sequences in it
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


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_ansi_terminal_tty(mocker, capsys) -> None:
    app = AnsiApp()
    mocker.patch.object(app.stdout, 'isatty', return_value=True)
    mocker.patch.object(sys.stderr, 'isatty', return_value=True)

    app.onecmd_plus_hooks('echo_error oopsie')
    # if colors are on, the output should have some ANSI style sequences in it
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


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_ansi_terminal_notty(mocker, capsys) -> None:
    app = AnsiApp()
    mocker.patch.object(app.stdout, 'isatty', return_value=False)
    mocker.patch.object(sys.stderr, 'isatty', return_value=False)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'


@with_ansi_style(ru.AllowStyle.NEVER)
def test_ansi_never_tty(mocker, capsys) -> None:
    app = AnsiApp()
    mocker.patch.object(app.stdout, 'isatty', return_value=True)
    mocker.patch.object(sys.stderr, 'isatty', return_value=True)

    app.onecmd_plus_hooks('echo_error oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'

    app.onecmd_plus_hooks('echo oopsie')
    out, err = capsys.readouterr()
    assert out == err == 'oopsie\n'


@with_ansi_style(ru.AllowStyle.NEVER)
def test_ansi_never_notty(mocker, capsys) -> None:
    app = AnsiApp()
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    @cmd2.with_category(category_name)
    def do_has_helper_funcs(self, arg) -> None:
        self.poutput("The real has_helper_funcs")

    def help_has_helper_funcs(self) -> None:
        self.poutput('Help for has_helper_funcs')

    def complete_has_helper_funcs(self, *args):
        return ['result']

    @cmd2.with_category(category_name)
    def do_has_no_helper_funcs(self, arg) -> None:
        """Help for has_no_helper_funcs"""
        self.poutput("The real has_no_helper_funcs")


@pytest.fixture
def disable_commands_app():
    return DisableCommandsApp()


def test_disable_and_enable_category(disable_commands_app) -> None:
    ##########################################################################
    # Disable the category
    ##########################################################################
    message_to_print = 'These commands are currently disabled'
    disable_commands_app.disable_category(disable_commands_app.category_name, message_to_print)

    # Make sure all the commands and help on those commands displays the message
    out, err = run_cmd(disable_commands_app, 'has_helper_funcs')
    assert err[0].startswith(message_to_print)

    out, err = run_cmd(disable_commands_app, 'help has_helper_funcs')
    assert err[0].startswith(message_to_print)

    out, err = run_cmd(disable_commands_app, 'has_no_helper_funcs')
    assert err[0].startswith(message_to_print)

    out, err = run_cmd(disable_commands_app, 'help has_no_helper_funcs')
    assert err[0].startswith(message_to_print)

    # Make sure neither function completes
    text = ''
    line = f'has_helper_funcs {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, disable_commands_app)
    assert first_match is None

    text = ''
    line = f'has_no_helper_funcs {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, disable_commands_app)
    assert first_match is None

    # Make sure both commands are invisible
    visible_commands = disable_commands_app.get_visible_commands()
    assert 'has_helper_funcs' not in visible_commands
    assert 'has_no_helper_funcs' not in visible_commands

    # Make sure get_help_topics() filters out disabled commands
    help_topics = disable_commands_app.get_help_topics()
    assert 'has_helper_funcs' not in help_topics

    ##########################################################################
    # Enable the category
    ##########################################################################
    disable_commands_app.enable_category(disable_commands_app.category_name)

    # Make sure all the commands and help on those commands are restored
    out, err = run_cmd(disable_commands_app, 'has_helper_funcs')
    assert out[0] == "The real has_helper_funcs"

    out, err = run_cmd(disable_commands_app, 'help has_helper_funcs')
    assert out[0] == "Help for has_helper_funcs"

    out, err = run_cmd(disable_commands_app, 'has_no_helper_funcs')
    assert out[0] == "The real has_no_helper_funcs"

    out, err = run_cmd(disable_commands_app, 'help has_no_helper_funcs')
    assert out[0] == "Help for has_no_helper_funcs"

    # has_helper_funcs should complete now
    text = ''
    line = f'has_helper_funcs {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, disable_commands_app)
    assert first_match is not None
    assert disable_commands_app.completion_matches == ['result ']

    # has_no_helper_funcs had no completer originally, so there should be no results
    text = ''
    line = f'has_no_helper_funcs {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, disable_commands_app)
    assert first_match is None

    # Make sure both commands are visible
    visible_commands = disable_commands_app.get_visible_commands()
    assert 'has_helper_funcs' in visible_commands
    assert 'has_no_helper_funcs' in visible_commands

    # Make sure get_help_topics() contains our help function
    help_topics = disable_commands_app.get_help_topics()
    assert 'has_helper_funcs' in help_topics


def test_enable_enabled_command(disable_commands_app) -> None:
    # Test enabling a command that is not disabled
    saved_len = len(disable_commands_app.disabled_commands)
    disable_commands_app.enable_command('has_helper_funcs')

    # The number of disabled_commands should not have changed
    assert saved_len == len(disable_commands_app.disabled_commands)


def test_disable_fake_command(disable_commands_app) -> None:
    with pytest.raises(AttributeError):
        disable_commands_app.disable_command('fake', 'fake message')


def test_disable_command_twice(disable_commands_app) -> None:
    saved_len = len(disable_commands_app.disabled_commands)
    message_to_print = 'These commands are currently disabled'
    disable_commands_app.disable_command('has_helper_funcs', message_to_print)

    # The length of disabled_commands should have increased one
    new_len = len(disable_commands_app.disabled_commands)
    assert saved_len == new_len - 1
    saved_len = new_len

    # Disable again and the length should not change
    disable_commands_app.disable_command('has_helper_funcs', message_to_print)
    new_len = len(disable_commands_app.disabled_commands)
    assert saved_len == new_len


def test_disabled_command_not_in_history(disable_commands_app) -> None:
    message_to_print = 'These commands are currently disabled'
    disable_commands_app.disable_command('has_helper_funcs', message_to_print)

    saved_len = len(disable_commands_app.history)
    run_cmd(disable_commands_app, 'has_helper_funcs')
    assert saved_len == len(disable_commands_app.history)


def test_disabled_message_command_name(disable_commands_app) -> None:
    message_to_print = f'{COMMAND_NAME} is currently disabled'
    disable_commands_app.disable_command('has_helper_funcs', message_to_print)

    _out, err = run_cmd(disable_commands_app, 'has_helper_funcs')
    assert err[0].startswith('has_helper_funcs is currently disabled')


@pytest.mark.parametrize('silence_startup_script', [True, False])
def test_startup_script(request, capsys, silence_startup_script) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    startup_script = os.path.join(test_dir, '.cmd2rc')
    app = cmd2.Cmd(allow_cli_args=False, startup_script=startup_script, silence_startup_script=silence_startup_script)
    assert len(app._startup_commands) == 1
    app._startup_commands.append('quit')
    app.cmdloop()

    out, _err = capsys.readouterr()
    if silence_startup_script:
        assert not out
    else:
        assert out

    out, _err = run_cmd(app, 'alias list')
    assert len(out) > 1
    assert 'alias create ls' in out[0]


@pytest.mark.parametrize('startup_script', odd_file_names)
def test_startup_script_with_odd_file_names(startup_script) -> None:
    """Test file names with various patterns"""
    # Mock os.path.exists to trick cmd2 into adding this script to its startup commands
    saved_exists = os.path.exists
    os.path.exists = mock.MagicMock(name='exists', return_value=True)

    app = cmd2.Cmd(allow_cli_args=False, startup_script=startup_script)
    assert len(app._startup_commands) == 1
    assert app._startup_commands[0] == f"run_script {su.quote(os.path.abspath(startup_script))}"

    # Restore os.path.exists
    os.path.exists = saved_exists


def test_transcripts_at_init() -> None:
    transcript_files = ['foo', 'bar']
    app = cmd2.Cmd(allow_cli_args=False, transcript_files=transcript_files)
    assert app._transcript_files == transcript_files


def test_command_parser_retrieval(outsim_app: cmd2.Cmd) -> None:
    # Pass something that isn't a method
    not_a_method = "just a string"
    assert outsim_app._command_parsers.get(not_a_method) is None

    # Pass a non-command method
    assert outsim_app._command_parsers.get(outsim_app.__init__) is None


def test_command_synonym_parser() -> None:
    # Make sure a command synonym returns the same parser as what it aliases
    class SynonymApp(cmd2.cmd2.Cmd):
        do_synonym = cmd2.cmd2.Cmd.do_help

    app = SynonymApp()

    synonym_parser = app._command_parsers.get(app.do_synonym)
    help_parser = app._command_parsers.get(app.do_help)

    assert synonym_parser is not None
    assert synonym_parser is help_parser
