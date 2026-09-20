"""Unit testing for cmd2/utils.py module."""

import contextlib
import errno
import math
import os
import signal
import sys
import time
from unittest import (
    mock,
)

import pytest

import cmd2.utils as cu

HELLO_WORLD = "Hello, world!"


def test_remove_duplicates_no_duplicates() -> None:
    no_dups = [5, 4, 3, 2, 1]
    assert cu.remove_duplicates(no_dups) == no_dups


def test_remove_duplicates_with_duplicates() -> None:
    duplicates = [1, 1, 2, 3, 9, 9, 7, 8]
    assert cu.remove_duplicates(duplicates) == [1, 2, 3, 9, 7, 8]


def test_alphabetical_sort() -> None:
    my_list = ["café", "µ", "A", "micro", "unity", "cafeteria"]
    assert cu.alphabetical_sort(my_list) == ["A", "cafeteria", "café", "micro", "unity", "µ"]
    my_list = ["a3", "a22", "A2", "A11", "a1"]
    assert cu.alphabetical_sort(my_list) == ["a1", "A11", "A2", "a22", "a3"]


def test_try_int_or_force_to_lower_case() -> None:
    str1 = "17"
    assert cu.try_int_or_force_to_lower_case(str1) == 17
    str1 = "ABC"
    assert cu.try_int_or_force_to_lower_case(str1) == "abc"
    str1 = "X19"
    assert cu.try_int_or_force_to_lower_case(str1) == "x19"
    str1 = ""
    assert cu.try_int_or_force_to_lower_case(str1) == ""


def test_natural_keys() -> None:
    my_list = ["café", "µ", "A", "micro", "unity", "x1", "X2", "X11", "X0", "x22"]
    my_list.sort(key=cu.natural_keys)
    assert my_list == ["A", "café", "micro", "unity", "X0", "x1", "X2", "X11", "x22", "µ"]
    my_list = ["a3", "a22", "A2", "A11", "a1"]
    my_list.sort(key=cu.natural_keys)
    assert my_list == ["a1", "A2", "a3", "A11", "a22"]


def test_natural_sort() -> None:
    my_list = ["café", "µ", "A", "micro", "unity", "x1", "X2", "X11", "X0", "x22"]
    assert cu.natural_sort(my_list) == ["A", "café", "micro", "unity", "X0", "x1", "X2", "X11", "x22", "µ"]
    my_list = ["a3", "a22", "A2", "A11", "a1"]
    assert cu.natural_sort(my_list) == ["a1", "A2", "a3", "A11", "a22"]


@pytest.fixture
def stdout_sim():
    return cu.StdSim(sys.stdout, echo=True)


def test_stdsim_write_str(stdout_sim) -> None:
    my_str = "Hello World"
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str


def test_stdsim_write_bytes(stdout_sim) -> None:
    b_str = b"Hello World"
    with pytest.raises(TypeError):
        stdout_sim.write(b_str)


def test_stdsim_buffer_write_bytes(stdout_sim) -> None:
    b_str = b"Hello World"
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getvalue() == b_str.decode()
    assert stdout_sim.getbytes() == b_str


def test_stdsim_buffer_write_str(stdout_sim) -> None:
    my_str = "Hello World"
    with pytest.raises(TypeError):
        stdout_sim.buffer.write(my_str)


def test_stdsim_read(stdout_sim) -> None:
    my_str = "Hello World"
    stdout_sim.write(my_str)
    # getvalue() returns the value and leaves it unaffected internally
    assert stdout_sim.getvalue() == my_str
    # read() returns the value and then clears the internal buffer
    assert stdout_sim.read() == my_str
    assert stdout_sim.getvalue() == ""

    stdout_sim.write(my_str)

    assert stdout_sim.getvalue() == my_str
    assert stdout_sim.read(2) == my_str[:2]
    assert stdout_sim.getvalue() == my_str[2:]


def test_stdsim_read_bytes(stdout_sim) -> None:
    b_str = b"Hello World"
    stdout_sim.buffer.write(b_str)
    # getbytes() returns the value and leaves it unaffected internally
    assert stdout_sim.getbytes() == b_str
    # read_bytes() returns the value and then clears the internal buffer
    assert stdout_sim.readbytes() == b_str
    assert stdout_sim.getbytes() == b""


def test_stdsim_clear(stdout_sim) -> None:
    my_str = "Hello World"
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str
    stdout_sim.clear()
    assert stdout_sim.getvalue() == ""


def test_stdsim_getattr_exist(stdout_sim) -> None:
    # Here the StdSim getattr is allowing us to access methods within StdSim
    my_str = "Hello World"
    stdout_sim.write(my_str)
    val_func = stdout_sim.getvalue
    assert val_func() == my_str


def test_stdsim_getattr_noexist(stdout_sim) -> None:
    # Here the StdSim getattr is allowing us to access methods defined by the inner stream
    assert not stdout_sim.isatty()


def test_stdsim_pause_storage(stdout_sim) -> None:
    # Test pausing storage for string data
    my_str = "Hello World"

    stdout_sim.pause_storage = False
    stdout_sim.write(my_str)
    assert stdout_sim.read() == my_str

    stdout_sim.pause_storage = True
    stdout_sim.write(my_str)
    assert stdout_sim.read() == ""

    # Test pausing storage for binary data
    b_str = b"Hello World"

    stdout_sim.pause_storage = False
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.readbytes() == b_str

    stdout_sim.pause_storage = True
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getbytes() == b""


def test_stdsim_line_buffering(base_app) -> None:
    # This exercises the case of writing binary data that contains new lines/carriage returns to a StdSim
    # when line buffering is on. The output should immediately be flushed to the underlying stream.
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="wt") as file:
        file.line_buffering = True

        stdsim = cu.StdSim(file, echo=True)
        saved_size = os.path.getsize(file.name)

        bytes_to_write = b"hello\n"
        stdsim.buffer.write(bytes_to_write)
        assert os.path.getsize(file.name) == saved_size + len(bytes_to_write)
        saved_size = os.path.getsize(file.name)

        bytes_to_write = b"hello\r"
        stdsim.buffer.write(bytes_to_write)
        assert os.path.getsize(file.name) == saved_size + len(bytes_to_write)


@pytest.fixture
def pr_none():
    import subprocess

    # Start a long running process so we have time to run tests on it before it finishes
    # Put the new process into a separate group so its signal are isolated from ours
    kwargs = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    # The child restores the default SIGINT action so that, like `sleep`, it dies with -SIGINT on POSIX
    child_code = "import signal, time; signal.signal(signal.SIGINT, signal.SIG_DFL); print('ready', flush=True); time.sleep(5)"
    proc = subprocess.Popen([sys.executable, "-c", child_code], stdout=subprocess.PIPE, **kwargs)

    # Wait for the child to report that it is running before returning it to a test. Signaling a Windows console
    # process before it has finished initializing makes it fail with STATUS_DLL_INIT_FAILED (0xc0000142) and pop up
    # an "Application Error" dialog that blocks the test run until someone clicks OK.
    assert proc.stdout.readline().strip() == b"ready"
    return cu.ProcReader(proc, sys.stdout, sys.stderr)


def test_proc_reader_send_sigint(pr_none) -> None:
    assert pr_none._proc.poll() is None
    pr_none.send_sigint()
    pr_none.wait()
    ret_code = pr_none._proc.poll()

    # Make sure a SIGINT killed the process
    if sys.platform.startswith("win"):
        assert ret_code is not None
    else:
        assert ret_code == -signal.SIGINT


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_proc_reader_does_not_resignal_its_own_group(pr_none) -> None:
    try:
        with mock.patch("os.getpgrp", return_value=pr_none._proc.pid), mock.patch("os.killpg") as killpg:
            pr_none.send_sigint()
        killpg.assert_not_called()
    finally:
        pr_none.terminate()
        pr_none.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_proc_reader_sigint_after_pipeline_exit() -> None:
    reader = cu.ProcReader(mock.Mock(pid=os.getpid() + 1, stdout=None, stderr=None), sys.stdout, sys.stderr)
    with (
        mock.patch("os.getpgid", side_effect=ProcessLookupError),
        mock.patch("os.killpg", side_effect=ProcessLookupError) as killpg,
    ):
        reader.send_sigint()
    killpg.assert_called_once_with(reader._proc.pid, signal.SIGINT)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_proc_reader_sigint_reaches_group_after_leader_exit() -> None:
    """A shell producer joins the pipeline's group and can outlive the consumer that led it."""
    import subprocess

    # A terminal pipeline leads its own group within our session, so a producer may join it.
    leader = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], process_group=0)
    reader = cu.ProcReader(leader, sys.stdout, sys.stderr)
    member_code = (
        "import signal, time; signal.signal(signal.SIGINT, signal.SIG_DFL); print('ready', flush=True); time.sleep(30)"
    )
    member = subprocess.Popen([sys.executable, "-c", member_code], stdout=subprocess.PIPE, process_group=leader.pid)
    try:
        assert member.stdout is not None
        assert member.stdout.readline().strip() == b"ready"
        reader.terminate()
        reader.wait()
        assert leader.returncode == -signal.SIGTERM

        reader.send_sigint()
        assert member.wait(timeout=5) == -signal.SIGINT
    finally:
        member.kill()
        member.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_proc_reader_terminal_group() -> None:
    proc = mock.Mock(pid=4242, returncode=None, stdout=None, stderr=None)
    assert cu.ProcReader(proc, sys.stdout, sys.stderr).terminal_group is None

    with mock.patch("os.tcgetpgrp", return_value=os.getpgrp()):
        reader = cu.ProcReader(proc, sys.stdout, sys.stderr, terminal_fd=0)
    assert reader.terminal_group == proc.pid
    proc.returncode = 0
    assert reader.terminal_group is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pipes")
@pytest.mark.parametrize("producer", ["writer", "child"])
def test_pipeline_writer_delivers_more_than_the_pipe_holds(producer) -> None:
    """Both cmd2's writes and a child inheriting the descriptor must wait for a slow consumer.

    A shell producer gets the descriptor itself, so it must stay blocking: a child that
    inherits O_NONBLOCK fails with EAGAIN once the pipe is full.
    """
    import subprocess
    import threading

    payload = b"x" * 4 * 1024 * 1024
    read_fd, write_fd = os.pipe()
    received = bytearray()

    def drain() -> None:
        while chunk := os.read(read_fd, 65536):
            received.extend(chunk)
            time.sleep(0.001)

    reader = mock.Mock(lend_terminal=contextlib.nullcontext)
    writer = cu.PipelineWriter(write_fd, reader)
    consumer = threading.Thread(target=drain)
    consumer.start()
    try:
        if producer == "writer":
            assert writer.write(payload) == len(payload)
        else:
            child = subprocess.run(
                [sys.executable, "-c", f"import sys; sys.stdout.buffer.write(b'x' * {len(payload)})"],
                stdout=writer.fileno(),
                stderr=subprocess.PIPE,
                check=False,
            )
            assert child.returncode == 0, child.stderr.decode()
    finally:
        writer.close()
        consumer.join()
        os.close(read_fd)
    assert bytes(received) == payload


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
    if sys.platform.startswith("win"):
        assert ret_code is not None
    else:
        assert ret_code == -signal.SIGTERM


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
@pytest.mark.parametrize("already_exited", [False, True])
def test_proc_reader_terminate_terminal_job(already_exited) -> None:
    proc = mock.Mock(stdout=None, stderr=None)
    reader = cu.ProcReader(proc, sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    with mock.patch("os.kill", side_effect=ProcessLookupError if already_exited else None) as kill:
        reader.terminate()
    kill.assert_called_once_with(proc.pid, signal.SIGTERM)
    # Only the job watcher may reap this process; Popen.terminate() would poll it.
    proc.terminate.assert_not_called()
    proc.poll.assert_not_called()
    proc.wait.assert_not_called()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
@pytest.mark.parametrize("stop_signal", ["SIGTTIN", "SIGTTOU"])
@pytest.mark.parametrize("expired_handoff", [False, True])
def test_proc_reader_resumes_terminal_access_after_handoff(stop_signal, expired_handoff) -> None:
    proc = mock.Mock(pid=123, stdout=None, stderr=None, returncode=None)
    reader = cu.ProcReader(proc, sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    reader._original_group = 456
    reader._terminal_available.set()
    stopped_status = (getattr(signal, stop_signal) << 8) | 0x7F
    handoffs = iter([False, True] if expired_handoff else [True])

    def handoff(timeout):
        assert timeout == 0.1
        if next(handoffs):
            reader._terminal_available.set()
        else:
            reader._terminal_available.clear()
        return True

    with (
        mock.patch(
            "os.waitpid",
            side_effect=[(proc.pid, stopped_status), *([(0, 0)] * (2 if expired_handoff else 1)), (proc.pid, 0)],
        ),
        mock.patch("os.tcgetpgrp", return_value=proc.pid),
        mock.patch.object(reader, "_set_foreground_group") as foreground,
        mock.patch.object(reader._terminal_available, "wait", side_effect=handoff) as available,
        mock.patch("os.killpg") as killpg,
        mock.patch("signal.raise_signal") as stop,
    ):
        reader._wait_for_job(10)
    assert available.call_count == (2 if expired_handoff else 1)
    killpg.assert_called_once_with(proc.pid, signal.SIGCONT)
    stop.assert_not_called()
    # The lend is still active: its holder returns the terminal, not the watcher.
    foreground.assert_not_called()
    assert proc.returncode == 0
    assert reader._process_done.is_set()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
@pytest.mark.parametrize("lent", [False, True])
def test_proc_reader_exit_returns_terminal_unless_lent(lent) -> None:
    """A shell producer in a lent pipeline group may outlive the consumer and still need the terminal."""
    proc = mock.Mock(pid=123, stdout=None, stderr=None, returncode=None)
    reader = cu.ProcReader(proc, sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    reader._original_group = 456
    if lent:
        reader._terminal_available.set()
    with (
        mock.patch("os.waitpid", return_value=(proc.pid, 0)),
        mock.patch("os.tcgetpgrp", return_value=proc.pid),
        mock.patch.object(reader, "_set_foreground_group") as foreground,
    ):
        reader._wait_for_job(10)
    if lent:
        foreground.assert_not_called()
    else:
        foreground.assert_called_once_with(10, reader._original_group)
    assert reader._process_done.is_set()


def test_proc_reader_wait_for_exit_without_terminal() -> None:
    proc = mock.Mock(stdout=None, stderr=None)
    reader = cu.ProcReader(proc, sys.stdout, sys.stderr)
    reader.wait_for_exit(timeout=0.2)
    proc.wait.assert_called_once_with(0.2)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
@pytest.mark.parametrize("handler_kind", ["default", "ignored", "custom"])
def test_proc_reader_suspend_restores_signal_handler(handler_kind) -> None:
    proc = mock.Mock(pid=123, stdout=None, stderr=None, returncode=None)
    reader = cu.ProcReader(proc, sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    reader._original_group = 456
    reader._terminal_available.set()
    previous = {"default": signal.SIG_DFL, "ignored": signal.SIG_IGN, "custom": mock.Mock()}[handler_kind]
    groups = [proc.pid, reader._original_group] if handler_kind == "default" else [reader._original_group]
    with (
        mock.patch("signal.getsignal", return_value=previous),
        mock.patch("signal.signal") as set_handler,
        mock.patch("signal.raise_signal") as stop,
        mock.patch("os.killpg") as killpg,
        mock.patch("os.tcgetpgrp", side_effect=groups),
        mock.patch("threading.Thread"),
        mock.patch.object(reader, "_set_foreground_group") as foreground,
        reader.manage_terminal(),
    ):
        handler = set_handler.call_args.args[1]
        handler(signal.SIGTSTP, None)
        assert reader._job_resumed.is_set()
    set_handler.assert_called_with(signal.SIGTSTP, previous)
    foreground.assert_called_with(10, proc.pid)
    if handler_kind == "default":
        killpg.assert_called_once_with(reader._original_group, signal.SIGTSTP)
        stop.assert_called_once_with(signal.SIGTSTP)
        assert set_handler.call_args_list == [
            mock.call(signal.SIGTSTP, handler),
            mock.call(signal.SIGTSTP, signal.SIG_IGN),
            mock.call(signal.SIGTSTP, signal.SIG_DFL),
            mock.call(signal.SIGTSTP, handler),
            mock.call(signal.SIGTSTP, previous),
        ]
    else:
        killpg.assert_not_called()
        stop.assert_not_called()
        if handler_kind == "custom":
            previous.assert_called_once_with(signal.SIGTSTP, None)


def test_proc_reader_captured_pipeline_needs_no_terminal() -> None:
    reader = cu.ProcReader(mock.Mock(stdout=None, stderr=None), sys.stdout, sys.stderr)
    with reader.manage_terminal(), reader.lend_terminal():
        assert not reader._terminal_available.is_set()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
def test_proc_reader_lending_restores_terminal_on_write_error() -> None:
    reader = cu.ProcReader(mock.Mock(pid=123, stdout=None, stderr=None, returncode=None), sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    reader._original_group = 456

    def failing_write():
        with reader.lend_terminal():
            assert reader._terminal_available.is_set()
            raise BrokenPipeError

    with (
        mock.patch("os.tcgetpgrp", return_value=123),
        mock.patch.object(reader, "_set_foreground_group") as foreground,
        pytest.raises(BrokenPipeError),
    ):
        failing_write()
    assert not reader._terminal_available.is_set()
    assert foreground.call_args_list == [mock.call(10, 123), mock.call(10, 456)]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
@pytest.mark.parametrize("error_number", [errno.ESRCH, errno.EINVAL, errno.EBADF])
def test_proc_reader_handoff_to_disappearing_group(error_number) -> None:
    reader = cu.ProcReader(mock.Mock(pid=123, stdout=None, stderr=None, returncode=None), sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    reader._original_group = 456

    def write():
        with reader.lend_terminal():
            assert reader._terminal_available.is_set()

    with (
        mock.patch("os.tcgetpgrp", return_value=456),
        mock.patch.object(reader, "_set_foreground_group", side_effect=OSError(error_number, "handoff failed")),
    ):
        if error_number == errno.EBADF:
            with pytest.raises(OSError, match="handoff failed"):
                write()
        else:
            write()
    assert not reader._terminal_available.is_set()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal job control")
def test_proc_reader_reaps_killed_consumer_without_another_handoff() -> None:
    proc = mock.Mock(pid=123, stdout=None, stderr=None, returncode=None)
    reader = cu.ProcReader(proc, sys.stdout, sys.stderr)
    reader._terminal_fd = 10
    reader._original_group = 456
    stopped_status = (signal.SIGTTIN << 8) | 0x7F
    with (
        mock.patch("os.waitpid", side_effect=[(123, stopped_status), (123, signal.SIGKILL)]),
        mock.patch("os.tcgetpgrp", return_value=456),
        mock.patch.object(reader._terminal_available, "wait", return_value=False),
        mock.patch("os.killpg") as killpg,
    ):
        reader._wait_for_job(10)
    assert proc.returncode == -signal.SIGKILL
    assert reader._process_done.is_set()
    killpg.assert_not_called()
    proc.wait.assert_not_called()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminal pipeline writer")
@pytest.mark.parametrize("returncode", [-signal.SIGINT, 128 + signal.SIGINT, 0])
@pytest.mark.parametrize("finished", [False, True])
def test_pipeline_writer_cancels_interrupted_producer_but_not_cleanup(returncode, finished) -> None:
    reader = cu.ProcReader(mock.Mock(stdout=None, stderr=None, returncode=returncode), sys.stdout, sys.stderr)
    if finished:
        reader.finish_producer()
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    expected = KeyboardInterrupt if returncode != 0 and not finished else BrokenPipeError
    with cu.PipelineWriter(write_fd, reader) as writer, pytest.raises(expected):
        writer.write(b"output")


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
    assert cu.to_bool("true")
    assert cu.to_bool("True")
    assert cu.to_bool("TRUE")
    assert cu.to_bool("tRuE")


def test_to_bool_str_false() -> None:
    assert not cu.to_bool("false")
    assert not cu.to_bool("False")
    assert not cu.to_bool("FALSE")
    assert not cu.to_bool("fAlSe")


def test_to_bool_str_invalid() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        cu.to_bool("other")


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
    assert cu.to_bool(-math.pi)
    assert not cu.to_bool(0)


def test_optional_int_none() -> None:
    assert cu.optional_int(None) is None
    assert cu.optional_int("none") is None
    assert cu.optional_int("None") is None
    assert cu.optional_int("nOnE") is None


def test_optional_int_int() -> None:
    assert cu.optional_int(5) == 5
    assert cu.optional_int("5") == 5
    assert cu.optional_int("-10") == -10


def test_optional_int_invalid() -> None:
    with pytest.raises(ValueError, match="must be an integer or None"):
        cu.optional_int("abc")
    with pytest.raises(ValueError, match="must be an integer or None"):
        cu.optional_int("3.14")
    with pytest.raises(ValueError, match="must be an integer or None"):
        cu.optional_int([])


def test_find_editor_specified() -> None:
    expected_editor = os.path.join("fake_dir", "editor")
    with mock.patch.dict(os.environ, {"EDITOR": expected_editor}):
        editor = cu.find_editor()
    assert editor == expected_editor


def test_find_editor_not_specified() -> None:
    # Use existing path env setting. Something in the editor list should be found.
    editor = cu.find_editor()
    assert editor

    # Overwrite path env setting with invalid path, clear all other env vars so no editor should be found.
    with mock.patch.dict(os.environ, {"PATH": "fake_dir"}, clear=True):
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
    assert suggested_command == "test"

    def custom_similarity_function(s1, s2) -> float:
        return 1.0 if "history" in (s1, s2) else 0.0

    suggested_command = cu.suggest_similar("test", options, similarity_function_to_use=custom_similarity_function)
    assert suggested_command == "history"

    suggested_command = cu.suggest_similar("history", options, similarity_function_to_use=custom_similarity_function)
    assert suggested_command == "history"

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
    assert param_name == "x"
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
    assert param_name == "x"
    assert param_value is bool


def test_categorize() -> None:
    from cmd2 import constants

    category = "Test Category"
    attr_name = constants.COMMAND_ATTR_HELP_CATEGORY

    # Test single function
    def func1() -> None:
        pass

    cu.categorize(func1, category)
    assert getattr(func1, attr_name) == category

    # Test single method
    class Foo:
        def foo_method(self) -> None:
            pass

    f = Foo()
    cu.categorize(f.foo_method, category)
    assert getattr(Foo.foo_method, attr_name) == category

    # Test iterable
    def func2() -> None:
        pass

    class Bar:
        def bar_method(self) -> None:
            pass

    b = Bar()
    cu.categorize([func2, b.bar_method], category)
    assert getattr(func2, attr_name) == category
    assert getattr(Bar.bar_method, attr_name) == category
