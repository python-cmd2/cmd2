"""Unit/functional testing for run_pytest in cmd2"""

import builtins
import os
from unittest import (
    mock,
)

import pytest

from cmd2.string_utils import quote

from .conftest import (
    odd_file_names,
    run_cmd,
)


def test_run_pyscript(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'script.py')
    expected = 'This is a python script running ...'

    out, _err = run_cmd(base_app, f"run_pyscript {python_script}")
    assert expected in out
    assert base_app.last_result is True


def test_run_pyscript_recursive_not_allowed(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'recursive.py')
    expected = 'Recursively entering interactive Python shells is not allowed'

    _out, err = run_cmd(base_app, f"run_pyscript {python_script}")
    assert err[0] == expected
    assert base_app.last_result is False


def test_run_pyscript_with_nonexist_file(base_app) -> None:
    python_script = 'does_not_exist.py'
    _out, err = run_cmd(base_app, f"run_pyscript {python_script}")
    assert "Error reading script file" in err[0]
    assert base_app.last_result is False


def test_run_pyscript_with_non_python_file(base_app, request) -> None:
    m = mock.MagicMock(name='input', return_value='2')
    builtins.input = m

    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'help.txt')
    _out, err = run_cmd(base_app, f'run_pyscript {filename}')
    assert "does not have a .py extension" in err[0]
    assert base_app.last_result is False


@pytest.mark.parametrize('python_script', odd_file_names)
def test_run_pyscript_with_odd_file_names(base_app, python_script) -> None:
    """Pass in file names with various patterns. Since these files don't exist, we will rely
    on the error text to make sure the file names were processed correctly.
    """
    # Mock input to get us passed the warning about not ending in .py
    input_mock = mock.MagicMock(name='input', return_value='1')
    builtins.input = input_mock

    _out, err = run_cmd(base_app, f"run_pyscript {quote(python_script)}")
    err = ''.join(err)
    assert f"Error reading script file '{python_script}'" in err
    assert base_app.last_result is False


def test_run_pyscript_with_exception(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'raises_exception.py')
    _out, err = run_cmd(base_app, f"run_pyscript {python_script}")
    assert err[0].startswith('Traceback')
    assert "TypeError: unsupported operand type(s) for +: 'int' and 'str'" in err[-1]
    assert base_app.last_result is True


def test_run_pyscript_requires_an_argument(base_app) -> None:
    _out, err = run_cmd(base_app, "run_pyscript")
    assert "the following arguments are required: script_path" in err[1]
    assert base_app.last_result is None


def test_run_pyscript_help(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    out1, _err1 = run_cmd(base_app, 'help')
    out2, _err2 = run_cmd(base_app, f'run_pyscript {python_script}')
    assert out1
    assert out1 == out2


def test_scripts_add_to_history(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    command = f'run_pyscript {python_script}'

    # Add to history
    base_app.scripts_add_to_history = True
    base_app.history.clear()
    run_cmd(base_app, command)
    assert len(base_app.history) == 2
    assert base_app.history.get(1).raw == command
    assert base_app.history.get(2).raw == 'help'

    # Do not add to history
    base_app.scripts_add_to_history = False
    base_app.history.clear()
    run_cmd(base_app, command)
    assert len(base_app.history) == 1
    assert base_app.history.get(1).raw == command


def test_run_pyscript_dir(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'pyscript_dir.py')

    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')
    assert out[0] == "['cmd_echo']"


def test_run_pyscript_capture(base_app, request) -> None:
    base_app.self_in_py = True
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'stdout_capture.py')
    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')

    assert out[0] == "print"
    assert out[1] == "poutput"


def test_run_pyscript_capture_custom_stdout(base_app, request) -> None:
    """sys.stdout will not be captured if it's different than self.stdout."""
    import io

    base_app.stdout = io.StringIO()

    base_app.self_in_py = True
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'stdout_capture.py')
    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')

    assert "print" not in out
    assert out[0] == "poutput"


def test_run_pyscript_stop(base_app, request) -> None:
    # Verify onecmd_plus_hooks() returns True if any commands in a pyscript return True for stop
    test_dir = os.path.dirname(request.module.__file__)

    # help.py doesn't run any commands that return True for stop
    python_script = os.path.join(test_dir, 'pyscript', 'help.py')
    stop = base_app.onecmd_plus_hooks(f'run_pyscript {python_script}')
    assert not stop

    # stop.py runs the quit command which does return True for stop
    python_script = os.path.join(test_dir, 'pyscript', 'stop.py')
    stop = base_app.onecmd_plus_hooks(f'run_pyscript {python_script}')
    assert stop


def test_run_pyscript_environment(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'environment.py')
    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')

    assert out[0] == "PASSED"


def test_run_pyscript_self_in_py(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'self_in_py.py')

    # Set self_in_py to True and make sure we see self
    base_app.self_in_py = True
    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')
    assert 'I see self' in out[0]

    # Set self_in_py to False and make sure we can't see self
    base_app.self_in_py = False
    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')
    assert 'I do not see self' in out[0]


def test_run_pyscript_py_locals(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'py_locals.py')

    # Make sure pyscripts can't edit Cmd.py_locals. It used to be that cmd2 was passing its py_locals
    # dictionary to the py environment instead of a shallow copy.
    base_app.py_locals['test_var'] = 5

    # Place an editable object in py_locals. Since we make a shallow copy of py_locals,
    # this object should be editable from the py environment.
    base_app.py_locals['my_list'] = []

    run_cmd(base_app, f'run_pyscript {python_script}')

    # test_var should still exist
    assert base_app.py_locals['test_var'] == 5

    # my_list should be edited
    assert base_app.py_locals['my_list'][0] == 2


def test_run_pyscript_app_echo(base_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'echo.py')
    out, _err = run_cmd(base_app, f'run_pyscript {python_script}')

    # Only the edit help text should have been echoed to pytest's stdout
    assert out[0] == "Usage: edit [-h] [file_path]"
