"""Command toolbar lifecycle and terminal integration tests."""

import io
import sys
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest
from prompt_toolkit.application import create_app_session, get_app
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.input.typeahead import get_typeahead
from prompt_toolkit.keys import Keys
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.shortcuts import PromptSession

from cmd2 import Cmd


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


class RecordingOutput(DummyOutput):
    def __init__(self, stream: Terminal) -> None:
        self.stdout = stream

    def write(self, data: str) -> None:
        self.stdout.write(data)

    def write_raw(self, data: str) -> None:
        self.stdout.write(data)


@pytest.fixture
def toolbar_app():
    app = Cmd(allow_cli_args=False)
    output = Terminal()
    app.stdout = output
    with create_pipe_input() as pipe:
        terminal = RecordingOutput(output)
        # Bind the ambient app session to this terminal. Without it, prompt-toolkit
        # builds a real one on demand for calls such as patch_stdout() in
        # _read_raw_input(), which needs a console that Windows CI does not provide.
        with create_app_session(input=pipe, output=terminal):
            app.main_session = PromptSession(
                input=pipe,
                output=terminal,
                bottom_toolbar="STATUS",
                refresh_interval=0.01,
            )
            yield app, pipe, output


def test_command_toolbar_refresh_and_output(toolbar_app, monkeypatch) -> None:
    app, _, output = toolbar_app
    refreshed = threading.Event()
    state = ["BEFORE"]
    threads = []

    def toolbar():
        threads.append(threading.current_thread())
        if state[0] == "AFTER":
            refreshed.set()
        return state[0]

    app.main_session.bottom_toolbar = toolbar
    monkeypatch.setattr(sys, "stdout", output)
    original_stderr = sys.stderr
    with app._command_toolbar_context():
        assert threading.current_thread() is threading.main_thread()
        assert get_app() is app._command_toolbar.app
        assert sys.stderr is original_stderr  # Keep redirected stderr separate.
        app.poutput("command output")
        print("standard output", end="")  # Flush unterminated output on exit.
        state[0] = "AFTER"
        assert refreshed.wait(2)

    assert "command output\n" in output.getvalue()
    assert "standard output" in output.getvalue()
    assert "AFTER" in output.getvalue()
    assert all(thread is not threading.main_thread() and not thread.is_alive() for thread in threads)
    assert app.stdout is output
    assert sys.stdout is output
    assert app._command_toolbar is None


def test_command_toolbar_redirected_output(toolbar_app, tmp_path) -> None:
    app, _, output = toolbar_app
    destination = tmp_path / "help.txt"
    with app._command_toolbar_context():
        app.onecmd_plus_hooks(f'help > "{destination}"')
    text = destination.read_text()
    assert "Cmd2 Commands" in text
    assert "STATUS" not in text
    assert "Cmd2 Commands" not in output.getvalue()


def test_command_toolbar_redirection_survives_suspension(toolbar_app, tmp_path) -> None:
    app, _, output = toolbar_app
    destination = tmp_path / "output.txt"

    def command(statement, **kwargs):
        app.poutput("before")
        with app.suspend_bottom_toolbar():
            app.poutput("during")
        app.poutput("after")
        return False

    with mock.patch.object(app, "onecmd", side_effect=command), app._command_toolbar_context():
        app.onecmd_plus_hooks(f'custom > "{destination}"')
        app.poutput("terminal output")

    assert destination.read_text() == "before\nduring\nafter\n"
    assert "before" not in output.getvalue()
    assert "during" not in output.getvalue()
    assert "after" not in output.getvalue()
    assert "terminal output" in output.getvalue()
    assert app.stdout is output


def test_command_toolbar_pipe_output(toolbar_app) -> None:
    app, _, output = toolbar_app
    with app._command_toolbar_context():
        app.onecmd_plus_hooks(f'help | "{sys.executable}" -c "import sys; print(sys.stdin.read().upper())"')
    assert "CMD2 COMMANDS" in output.getvalue()


class FileTerminal:
    """A real file that claims to be a terminal, so it owns a descriptor a subprocess can inherit."""

    def __init__(self, file) -> None:
        self.file = file

    def isatty(self) -> bool:
        return True

    def __getattr__(self, name):
        return getattr(self.file, name)


def test_command_toolbar_pipe_process_inherits_terminal(toolbar_app, tmp_path) -> None:
    app, _, _ = toolbar_app
    destination = tmp_path / "terminal.txt"
    running = []
    readers = []

    def command(statement, **kwargs):
        # The pipe process owns the terminal, so the toolbar must have stepped aside.
        running.append(app._command_toolbar.app.is_running)
        readers.append(app._cur_pipe_proc_reader)
        app.poutput("piped")
        return False

    with destination.open("w+") as handle:
        app.stdout = FileTerminal(handle)
        with mock.patch.object(app, "onecmd", side_effect=command), app._command_toolbar_context():
            app.onecmd_plus_hooks(f'custom | "{sys.executable}" -c "import sys; sys.stdout.write(sys.stdin.read().upper())"')
            # The terminal goes back to the toolbar once the pipe process has exited.
            assert app._command_toolbar.app.is_running
            assert app.stdout.proxy is not None

    assert running == [False]
    # A process given the terminal writes to it directly instead of through a captured pipe.
    assert readers[0]._proc.stdout is None
    assert "PIPED" in destination.read_text()


def test_command_toolbar_binary_output(toolbar_app) -> None:
    app, _, output = toolbar_app
    data = "Unicode: 😇\n".encode()
    with app._command_toolbar_context():
        for byte in data:
            app.stdout.buffer.write(bytes([byte]))
        app.stdout.buffer.flush()
    assert "Unicode: 😇\n" in output.getvalue()


def test_command_toolbar_interrupt_uses_signal_handler(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    interrupted = threading.Event()
    signal_target = "_thread.interrupt_main" if sys.platform == "win32" else "cmd2.command_toolbar.os.killpg"
    with mock.patch(signal_target, side_effect=lambda *_: interrupted.set()) as interrupt:
        with app._command_toolbar_context():
            pipe.send_text("\x03")
            assert interrupted.wait(2)
        interrupt.assert_called_once()
        if sys.platform != "win32":
            # Reach subprocesses a command started, as the terminal driver would.
            import os
            import signal

            assert interrupt.call_args.args == (os.getpgrp(), signal.SIGINT)


def test_command_toolbar_interrupt_discards_cancelled_typeahead(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    interrupted = threading.Event()
    received = threading.Event()
    signal_target = "_thread.interrupt_main" if sys.platform == "win32" else "cmd2.command_toolbar.os.killpg"
    with mock.patch(signal_target, side_effect=lambda *_: interrupted.set()), app._command_toolbar_context():
        toolbar = app._command_toolbar

        def key_processed(_):
            if "".join(key.data for key in toolbar._keys).endswith("kept\n"):
                received.set()

        toolbar.app.key_processor.after_key_press += key_processed
        pipe.send_text("cancelled\n\x03")
        assert interrupted.wait(2)
        # Input entered after the interrupt should still reach the next prompt.
        pipe.send_text("kept\n")
        assert received.wait(2)

    assert app._read_raw_input("Next: ", app.main_session) == "kept"


@pytest.mark.parametrize(("supported", "enabled"), [(True, True), (True, False), (False, True)])
def test_command_toolbar_ctrl_z(toolbar_app, supported, enabled) -> None:
    app, pipe, _ = toolbar_app
    app.main_session.enable_suspend = enabled
    processed = threading.Event()
    with (
        mock.patch("cmd2.command_toolbar.suspend_to_background_supported", return_value=supported),
        app._command_toolbar_context(),
    ):
        toolbar = app._command_toolbar
        toolbar.app.key_processor.after_key_press += lambda _: processed.set()
        with mock.patch.object(toolbar.app, "suspend_to_background") as suspend:
            pipe.send_text("\x1a")
            assert processed.wait(2)
            if supported and enabled:
                suspend.assert_called_once_with()
            else:
                suspend.assert_not_called()

    keys = get_typeahead(pipe)
    assert [key.key for key in keys] == ([] if supported and enabled else [Keys.ControlZ])


def test_command_toolbar_script_output_has_no_batching_delay(toolbar_app) -> None:
    app, _, output = toolbar_app
    sleep = mock.Mock()

    def command(statement, **kwargs):
        app.poutput("script output")
        return False

    # Observe requested sleeps instead of depending on the machine's execution speed.
    with (
        mock.patch("prompt_toolkit.patch_stdout.time", SimpleNamespace(sleep=sleep)),
        mock.patch.object(app, "onecmd", side_effect=command),
        app._command_toolbar_context(),
    ):
        app.runcmds_plus_hooks(["custom"] * 10)

    assert output.getvalue().count("script output\n") == 10
    assert all(call.args[0] == 0 for call in sleep.call_args_list)


def test_command_toolbar_suspension_and_nested_input(toolbar_app) -> None:
    app, pipe, output = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        with app.suspend_bottom_toolbar():
            assert not toolbar.app.is_running
            assert app.stdout.original is output
            assert app.stdout.proxy is None
            with app.suspend_bottom_toolbar():
                assert not toolbar.app.is_running
        assert toolbar.app.is_running

        # Feed the nested prompt only after it has taken ownership of input.
        result = app._read_raw_input("Value: ", app.main_session, pre_run=lambda: pipe.send_text("answer\n"))
        assert result == "answer"
        assert toolbar.app.is_running


class CprOutput(RecordingOutput):
    """A terminal that asks for cursor position reports and never answers them."""

    def get_rows_below_cursor_position(self) -> int:
        raise NotImplementedError

    @property
    def responds_to_cpr(self) -> bool:
        return True


def test_command_toolbar_flushes_writes_waiting_on_cursor_reports() -> None:
    app = Cmd(allow_cli_args=False)
    output = Terminal()
    app.stdout = output

    with create_pipe_input() as pipe:
        app.main_session = PromptSession(
            input=pipe,
            output=CprOutput(output),
            bottom_toolbar="STATUS",
            refresh_interval=0.01,
        )
        # Terminal writes wait for a pending cursor position report, so stopping the
        # display must not cancel them out from under the text.
        with app._command_toolbar_context():
            app.poutput("last words")

    assert "last words\n" in output.getvalue()


def test_command_toolbar_suspension_waits_for_in_flight_writes(toolbar_app) -> None:
    app, _, output = toolbar_app
    writing = threading.Event()

    with app._command_toolbar_context():
        proxy = app._command_toolbar._proxy
        proxy_write = proxy.write

        def slow_write(data: str) -> int:
            # Widen the window in which suspending could close this proxy. A closed
            # proxy accepts writes and discards them, so the output would vanish.
            writing.set()
            time.sleep(0.1)
            return proxy_write(data)

        proxy.write = slow_write
        thread = threading.Thread(target=lambda: app.poutput("in flight"))
        thread.start()
        assert writing.wait(2)

        # A command reaches this at every finalization boundary while its own
        # threads are still printing.
        with app.suspend_bottom_toolbar():
            pass
        thread.join()

    assert "in flight\n" in output.getvalue()


def test_command_toolbar_typeahead(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    received = threading.Event()
    with app._command_toolbar_context():
        toolbar = app._command_toolbar

        def key_processed(_):
            if len(toolbar._keys) == len("next\n"):
                received.set()

        toolbar.app.key_processor.after_key_press += key_processed
        pipe.send_text("next\n")
        assert received.wait(2)

    assert app._read_raw_input("Next: ", app.main_session) == "next"


def test_command_toolbar_typeahead_preserves_pending_input_order(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    exiting = threading.Event()
    with app._command_toolbar_context():
        toolbar = app._command_toolbar

        def exit_after_first_key(_):
            # Leave the remaining keys in prompt-toolkit's queue, as happens when
            # input arrives just as a command finishes.
            toolbar.app.exit()
            exiting.set()

        toolbar.app.key_processor.after_key_press += exit_after_first_key
        pipe.send_text("ab\n")
        assert exiting.wait(2)
        toolbar._thread.join(timeout=2)
        assert not toolbar._thread.is_alive()

    assert app._read_raw_input("Next: ", app.main_session) == "ab"


@pytest.mark.parametrize("exception", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_command_toolbar_cleanup_on_exception(toolbar_app, exception) -> None:
    app, _, output = toolbar_app
    threads = []

    def run_command():
        with app._command_toolbar_context():
            threads.append(app._command_toolbar._thread)
            raise exception

    with pytest.raises(exception):
        run_command()
    assert len(threads) == 1
    assert not threads[0].is_alive()
    assert app.stdout is output
    assert app._command_toolbar is None


def test_command_toolbar_recovers_from_stop_failure(toolbar_app) -> None:
    app, _, _ = toolbar_app

    context = app._command_toolbar_context()
    context.__enter__()
    toolbar = app._command_toolbar
    real_stop = toolbar.stop

    def failing_stop() -> None:
        # Tear down for real, then fail the way a broken stream close would.
        real_stop()
        raise RuntimeError("broken stop")

    toolbar.stop = failing_stop
    with pytest.raises(RuntimeError, match="broken stop"):
        context.__exit__(None, None, None)

    # A later command still gets a toolbar instead of being locked out by the dead one.
    assert app._command_toolbar is None
    with app._command_toolbar_context():
        assert app._command_toolbar is not None
        assert app._command_toolbar is not toolbar
    assert app._command_toolbar is None


def test_command_toolbar_failure_after_startup_is_reported(toolbar_app, capsys) -> None:
    app, _, output = toolbar_app

    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        # Stop the display the way an unhandled error in its own thread would, after
        # _resume() has already returned and can no longer raise for the command.
        toolbar.app.loop.call_soon_threadsafe(lambda: toolbar.app.exit(exception=ValueError("broken display")))
        toolbar._thread.join(timeout=2)
        assert not toolbar._thread.is_alive()

        # Output must still reach the terminal rather than a proxy nothing is draining.
        assert all(stream.proxy is None for stream in toolbar._streams)
        app.poutput("after failure")

    assert "broken display" in capsys.readouterr().err
    assert "after failure\n" in output.getvalue()


def test_command_toolbar_render_failure(toolbar_app) -> None:
    app, _, output = toolbar_app

    def broken_toolbar():
        raise ValueError("broken toolbar")

    app.main_session.bottom_toolbar = broken_toolbar
    with pytest.raises(ValueError, match="broken toolbar"), app._command_toolbar_context():
        pytest.fail("Command should not run after a toolbar startup failure")
    assert app.stdout is output
    assert app._command_toolbar is None


@pytest.mark.parametrize("enabled", [False, True])
def test_command_toolbar_headless(enabled) -> None:
    app = Cmd(allow_cli_args=False, enable_bottom_toolbar=enabled)
    with mock.patch("cmd2.command_toolbar.CommandToolbar") as toolbar, app._command_toolbar_context():
        toolbar.assert_not_called()


def test_cmdloop_runs_commands_with_toolbar(toolbar_app, monkeypatch) -> None:
    app, _, _ = toolbar_app
    monkeypatch.setattr(app, "_read_command_line", lambda _: "quit")
    commands = []

    def command(line, **kwargs):
        assert threading.current_thread() is threading.main_thread()
        assert app._command_toolbar.app.is_running
        commands.append(line)
        return line == "quit"

    app._startup_commands = ["startup"]
    monkeypatch.setattr(app, "onecmd_plus_hooks", command)
    app._cmdloop()
    assert commands == ["startup", "quit"]
