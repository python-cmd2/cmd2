"""Unit testing for cmd2/utils.py module."""

import os
import signal
import sys
import time
from unittest import (
    mock,
)

import pytest

import cmd2.utils as cu

HELLO_WORLD = 'Hello, world!'


def test_remove_duplicates_no_duplicates() -> None:
    no_dups = [5, 4, 3, 2, 1]
    assert cu.remove_duplicates(no_dups) == no_dups


def test_remove_duplicates_with_duplicates() -> None:
    duplicates = [1, 1, 2, 3, 9, 9, 7, 8]
    assert cu.remove_duplicates(duplicates) == [1, 2, 3, 9, 7, 8]


def test_alphabetical_sort() -> None:
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'cafeteria']
    assert cu.alphabetical_sort(my_list) == ['A', 'cafeteria', 'café', 'micro', 'unity', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.alphabetical_sort(my_list) == ['a1', 'A11', 'A2', 'a22', 'a3']


def test_try_int_or_force_to_lower_case() -> None:
    str1 = '17'
    assert cu.try_int_or_force_to_lower_case(str1) == 17
    str1 = 'ABC'
    assert cu.try_int_or_force_to_lower_case(str1) == 'abc'
    str1 = 'X19'
    assert cu.try_int_or_force_to_lower_case(str1) == 'x19'
    str1 = ''
    assert cu.try_int_or_force_to_lower_case(str1) == ''


def test_natural_keys() -> None:
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['a1', 'A2', 'a3', 'A11', 'a22']


def test_natural_sort() -> None:
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    assert cu.natural_sort(my_list) == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.natural_sort(my_list) == ['a1', 'A2', 'a3', 'A11', 'a22']


@pytest.fixture
def stdout_sim():
    return cu.StdSim(sys.stdout, echo=True)


def test_stdsim_write_str(stdout_sim) -> None:
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str


def test_stdsim_write_bytes(stdout_sim) -> None:
    b_str = b'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.write(b_str)


def test_stdsim_buffer_write_bytes(stdout_sim) -> None:
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getvalue() == b_str.decode()
    assert stdout_sim.getbytes() == b_str


def test_stdsim_buffer_write_str(stdout_sim) -> None:
    my_str = 'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.buffer.write(my_str)


def test_stdsim_read(stdout_sim) -> None:
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    # getvalue() returns the value and leaves it unaffected internally
    assert stdout_sim.getvalue() == my_str
    # read() returns the value and then clears the internal buffer
    assert stdout_sim.read() == my_str
    assert stdout_sim.getvalue() == ''

    stdout_sim.write(my_str)

    assert stdout_sim.getvalue() == my_str
    assert stdout_sim.read(2) == my_str[:2]
    assert stdout_sim.getvalue() == my_str[2:]


def test_stdsim_read_bytes(stdout_sim) -> None:
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    # getbytes() returns the value and leaves it unaffected internally
    assert stdout_sim.getbytes() == b_str
    # read_bytes() returns the value and then clears the internal buffer
    assert stdout_sim.readbytes() == b_str
    assert stdout_sim.getbytes() == b''


def test_stdsim_clear(stdout_sim) -> None:
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str
    stdout_sim.clear()
    assert stdout_sim.getvalue() == ''


def test_stdsim_getattr_exist(stdout_sim) -> None:
    # Here the StdSim getattr is allowing us to access methods within StdSim
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    val_func = stdout_sim.getvalue
    assert val_func() == my_str


def test_stdsim_getattr_noexist(stdout_sim) -> None:
    # Here the StdSim getattr is allowing us to access methods defined by the inner stream
    assert not stdout_sim.isatty()


def test_stdsim_pause_storage(stdout_sim) -> None:
    # Test pausing storage for string data
    my_str = 'Hello World'

    stdout_sim.pause_storage = False
    stdout_sim.write(my_str)
    assert stdout_sim.read() == my_str

    stdout_sim.pause_storage = True
    stdout_sim.write(my_str)
    assert stdout_sim.read() == ''

    # Test pausing storage for binary data
    b_str = b'Hello World'

    stdout_sim.pause_storage = False
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.readbytes() == b_str

    stdout_sim.pause_storage = True
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getbytes() == b''


def test_stdsim_line_buffering(base_app) -> None:
    # This exercises the case of writing binary data that contains new lines/carriage returns to a StdSim
    # when line buffering is on. The output should immediately be flushed to the underlying stream.
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode='wt') as file:
        file.line_buffering = True

        stdsim = cu.StdSim(file, echo=True)
        saved_size = os.path.getsize(file.name)

        bytes_to_write = b'hello\n'
        stdsim.buffer.write(bytes_to_write)
        assert os.path.getsize(file.name) == saved_size + len(bytes_to_write)
        saved_size = os.path.getsize(file.name)

        bytes_to_write = b'hello\r'
        stdsim.buffer.write(bytes_to_write)
        assert os.path.getsize(file.name) == saved_size + len(bytes_to_write)


@pytest.fixture
def pr_none():
    import subprocess

    # Start a long running process so we have time to run tests on it before it finishes
    # Put the new process into a separate group so its signal are isolated from ours
    kwargs = {}
    if sys.platform.startswith('win'):
        command = 'timeout -t 5 /nobreak'
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        command = 'sleep 5'
        kwargs['start_new_session'] = True

    proc = subprocess.Popen(command, shell=True, **kwargs)
    return cu.ProcReader(proc, None, None)


def test_proc_reader_send_sigint(pr_none) -> None:
    assert pr_none._proc.poll() is None
    pr_none.send_sigint()
    pr_none.wait()
    ret_code = pr_none._proc.poll()

    # Make sure a SIGINT killed the process
    if sys.platform.startswith('win'):
        assert ret_code is not None
    else:
        assert ret_code == -signal.SIGINT


def test_proc_reader_terminate(pr_none) -> None:
    assert pr_none._proc.poll() is None
    pr_none.terminate()

    wait_start = time.monotonic()
    pr_none.wait()
    wait_finish = time.monotonic()

    # Make sure the process exited before sleep of 5 seconds finished
    # 3 seconds accounts for some delay but is long enough for the process to exit
    assert wait_finish - wait_start < 3

    ret_code = pr_none._proc.poll()
    if sys.platform.startswith('win'):
        assert ret_code is not None
    else:
        assert ret_code == -signal.SIGTERM


@pytest.fixture
def context_flag():
    return cu.ContextFlag()


def test_context_flag_bool(context_flag) -> None:
    assert not context_flag
    with context_flag:
        assert context_flag


def test_context_flag_exit_err(context_flag) -> None:
    with pytest.raises(ValueError, match="count has gone below 0"):
        context_flag.__exit__()


def test_to_bool_str_true() -> None:
    assert cu.to_bool('true')
    assert cu.to_bool('True')
    assert cu.to_bool('TRUE')
    assert cu.to_bool('tRuE')


def test_to_bool_str_false() -> None:
    assert not cu.to_bool('false')
    assert not cu.to_bool('False')
    assert not cu.to_bool('FALSE')
    assert not cu.to_bool('fAlSe')


def test_to_bool_str_invalid() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        cu.to_bool('other')


def test_to_bool_bool() -> None:
    assert cu.to_bool(True)
    assert not cu.to_bool(False)


def test_to_bool_int() -> None:
    assert cu.to_bool(1)
    assert cu.to_bool(-1)
    assert not cu.to_bool(0)


def test_to_bool_float() -> None:
    assert cu.to_bool(2.35)
    assert cu.to_bool(0.25)
    assert cu.to_bool(-3.1415)
    assert not cu.to_bool(0)


def test_find_editor_specified() -> None:
    expected_editor = os.path.join('fake_dir', 'editor')
    with mock.patch.dict(os.environ, {'EDITOR': expected_editor}):
        editor = cu.find_editor()
    assert editor == expected_editor


def test_find_editor_not_specified() -> None:
    # Use existing path env setting. Something in the editor list should be found.
    editor = cu.find_editor()
    assert editor

    # Overwrite path env setting with invalid path, clear all other env vars so no editor should be found.
    with mock.patch.dict(os.environ, {'PATH': 'fake_dir'}, clear=True):
        editor = cu.find_editor()
    assert editor is None


def test_similarity() -> None:
    suggested_command = cu.suggest_similar("comand", ["command", "UNRELATED", "NOT_SIMILAR"])
    assert suggested_command == "command"
    suggested_command = cu.suggest_similar("command", ["COMMAND", "acommands"])
    assert suggested_command == "COMMAND"


def test_similarity_without_good_canididates() -> None:
    suggested_command = cu.suggest_similar("comand", ["UNRELATED", "NOT_SIMILAR"])
    assert suggested_command is None
    suggested_command = cu.suggest_similar("comand", [])
    assert suggested_command is None


def test_similarity_overwrite_function() -> None:
    options = ["history", "test"]
    suggested_command = cu.suggest_similar("test", options)
    assert suggested_command == 'test'

    def custom_similarity_function(s1, s2) -> float:
        return 1.0 if 'history' in (s1, s2) else 0.0

    suggested_command = cu.suggest_similar("test", options, similarity_function_to_use=custom_similarity_function)
    assert suggested_command == 'history'

    suggested_command = cu.suggest_similar("history", options, similarity_function_to_use=custom_similarity_function)
    assert suggested_command == 'history'

    suggested_command = cu.suggest_similar("test", ["test"], similarity_function_to_use=custom_similarity_function)
    assert suggested_command is None


def test_get_types_invalid_input() -> None:
    x = 1
    with pytest.raises(ValueError, match="Argument passed to get_types should be a function or method"):
        cu.get_types(x)


def test_get_types_empty() -> None:
    def a(b):
        print(b)

    param_ann, ret_ann = cu.get_types(a)
    assert ret_ann is None
    assert param_ann == {}


def test_get_types_non_empty() -> None:
    def foo(x: int) -> str:
        return f"{x * x}"

    param_ann, ret_ann = cu.get_types(foo)
    assert ret_ann is str
    param_name, param_value = next(iter(param_ann.items()))
    assert param_name == 'x'
    assert param_value is int


def test_get_types_method() -> None:
    class Foo:
        def bar(self, x: bool) -> None:
            print(x)

    f = Foo()

    param_ann, ret_ann = cu.get_types(f.bar)
    assert ret_ann is None
    assert len(param_ann) == 1
    param_name, param_value = next(iter(param_ann.items()))
    assert param_name == 'x'
    assert param_value is bool
