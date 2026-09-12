"""Command toolbar lifecycle and terminal integration tests."""

import contextlib
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from types import SimpleNamespace
from unittest import mock

import pytest
from prompt_toolkit.application import get_app
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.input.typeahead import get_typeahead
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.shortcuts import PromptSession

from cmd2 import Cmd, ToolbarMode, command_toolbar

from .conftest import ContendedLock, RecordingOutput, Terminal


def test_command_toolbar_refresh_and_output(toolbar_app, monkeypatch) -> None:
    app, _, output = toolbar_app
    refreshed = threading.Event()
    state = ["BEFORE"]
    threads = []

    def toolbar():
        threads.append(threading.current_thread())
        return state[0]

    def after_render(ui):
        # Content evaluation precedes drawing. Wait for the completed frame, and
        # inspect its cells: BEFORE and AFTER share the R in column five, so a
        # correct incremental redraw may emit only AFTE rather than the whole word.
        screen = ui.renderer._last_screen
        if screen is not None:
            size = ui.output.get_size()
            band = "".join(screen.data_buffer[size.rows - 1][x].char for x in range(size.columns))
            if band.rstrip() == "AFTER":
                refreshed.set()

    app.main_session.bottom_toolbar = toolbar
    app.main_session.app.after_render += after_render
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
    assert all(thread is not threading.main_thread() and not thread.is_alive() for thread in threads)
    assert app.stdout is output
    assert sys.stdout is output
    assert app._command_toolbar is None


def test_command_toolbar_redirected_output(toolbar_app, tmp_path) -> None:
    app, _, output = toolbar_app
    destination = tmp_path / "help.txt"
    with app._command_toolbar_context():
        app.onecmd_plus_hooks(f'help > "{destination}"')
    text = destination.read_text(encoding="utf-8")
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

    assert destination.read_text(encoding="utf-8") == "before\nduring\nafter\n"
    assert "before" not in output.getvalue()
    assert "during" not in output.getvalue()
    assert "after" not in output.getvalue()
    assert "terminal output" in output.getvalue()
    assert app.stdout is output


def test_command_toolbar_pipe_output(toolbar_app, running_pipe_process) -> None:
    # The child needs only sys; -S skips site initialization while retaining real pipe I/O.
    app, _, output = toolbar_app
    with app._command_toolbar_context():
        app.onecmd_plus_hooks(f'help | "{sys.executable}" -S -c "import sys; print(sys.stdin.read().upper())"')
    assert "CMD2 COMMANDS" in output.getvalue()


class FileTerminal:
    """A real file that claims to be a terminal, so it owns a descriptor a subprocess can inherit."""

    def __init__(self, file) -> None:
        self.file = file

    def isatty(self) -> bool:
        return True

    def __getattr__(self, name):
        return getattr(self.file, name)


@pytest.mark.parametrize(("stdout_tty", "stderr_tty"), [(False, False), (True, False), (False, True), (True, True)])
def test_pipeline_process_group_selection(toolbar_app, tmp_path, monkeypatch, running_pipe_process, stdout_tty, stderr_tty):
    app, _, _ = toolbar_app
    with (tmp_path / "stdout").open("w+") as out, (tmp_path / "stderr").open("w+") as err:
        app.stdout = FileTerminal(out) if stdout_tty else out
        monkeypatch.setattr(sys, "stderr", FileTerminal(err) if stderr_tty else err)
        with mock.patch("subprocess.Popen", wraps=subprocess.Popen) as popen:
            app.onecmd_plus_hooks(f'help | "{sys.executable}" -S -c "import sys; print(sys.stdin.read())"')
        options = popen.call_args.kwargs
        if sys.platform == "win32":
            assert options["creationflags"] == subprocess.CREATE_NEW_PROCESS_GROUP
            assert "start_new_session" not in options
        else:
            # A stream claiming isatty() is insufficient: these files do not
            # refer to our controlling terminal, so no foreground handoff is safe.
            assert options["start_new_session"]
            assert "process_group" not in options


@pytest.mark.parametrize("builtin_pager", [False, True])
def test_command_toolbar_pipe_process_inherits_terminal(toolbar_app, tmp_path, builtin_pager, running_pipe_process) -> None:
    app, _, _ = toolbar_app
    app.use_builtin_pager = builtin_pager
    destination = tmp_path / "terminal.txt"
    running = []
    readers = []

    def command(statement, **kwargs):
        # The pipe process owns the terminal, so the toolbar must have stepped aside.
        running.append(app._command_toolbar.app.is_running)
        assert app.main_session.app.layout is app.main_session.layout
        readers.append(app._cur_pipe_proc_reader)
        app.ppaged("piped")
        return False

    with destination.open("w+") as handle:
        app.stdout = FileTerminal(handle)
        with mock.patch.object(app, "onecmd", side_effect=command), app._command_toolbar_context():
            app.onecmd_plus_hooks(
                f'custom | "{sys.executable}" -S -c "import sys; sys.stdout.write(sys.stdin.read().upper())"'
            )
            # The terminal goes back to the toolbar once the pipe process has exited.
            assert app._command_toolbar.app.is_running
            assert app.stdout.proxy is not None

    assert running == [False]
    # A process given the terminal writes to it directly instead of through a captured pipe.
    assert readers[0]._proc.stdout is None
    assert "PIPED" in destination.read_text(encoding="utf-8")


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


def test_command_toolbar_flushes_writes_waiting_on_cursor_reports(monkeypatch) -> None:
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
        # Keep a real unanswered request, but expire its shutdown wait promptly.
        # This test checks that queued output survives expiry, not the timeout duration.
        renderer = app.main_session.app.renderer
        wait_for_cpr = renderer.wait_for_cpr_responses

        async def expire_cpr() -> None:
            await wait_for_cpr(timeout=0.01)

        monkeypatch.setattr(renderer, "wait_for_cpr_responses", expire_cpr)
        # Terminal writes wait for a pending cursor position report, so stopping the
        # display must not cancel them out from under the text.
        with app._command_toolbar_context():
            app.poutput("last words")

    assert "last words\n" in output.getvalue()


def test_command_toolbar_suspension_waits_for_in_flight_writes(toolbar_app, monkeypatch) -> None:
    app, _, output = toolbar_app
    writing = threading.Event()
    observed = ContendedLock()
    original_init = command_toolbar.CommandToolbar.__init__

    def init(display, *args, **kwargs):
        original_init(display, *args, **kwargs)
        display._lock = observed

    monkeypatch.setattr(command_toolbar.CommandToolbar, "__init__", init)

    with app._command_toolbar_context():
        proxy = app._command_toolbar._proxy
        proxy_write = proxy.write

        def slow_write(data: str) -> int:
            # Do not finish the write until suspension actually tries to take its lock.
            writing.set()
            assert observed.contended.wait(5), "pause did not wait for the writer"
            return proxy_write(data)

        proxy.write = slow_write
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(app.poutput, "in flight")
            assert writing.wait(5)
            with app.suspend_bottom_toolbar():
                pass
            pending.result(timeout=5)

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
        toolbar.app.key_processor.after_key_press -= exit_after_first_key

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
    app, pipe, _ = toolbar_app
    bindings = app.main_session.app.key_bindings

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
    assert app.main_session.app.layout is app.main_session.layout
    assert app.main_session.app.key_bindings is bindings
    with app._command_toolbar_context():
        assert app._command_toolbar is not None
        assert app._command_toolbar is not toolbar
    assert app._command_toolbar is None
    assert app._read_raw_input("Next: ", app.main_session, pre_run=lambda: pipe.send_text("recovered\n")) == "recovered"


def test_command_toolbar_exit_after_result_is_set(toolbar_app) -> None:
    app, _, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar

        def already_exiting():
            toolbar.app.exit()
            # The result is set before run_async() has finished its cleanup.
            assert toolbar.app.is_running
            toolbar._exit()

        toolbar._call_in_ui(already_exiting)
    assert app.main_session.app.layout is app.main_session.layout


def test_command_toolbar_ui_call_propagates_failures(toolbar_app, monkeypatch) -> None:
    app, _, _ = toolbar_app

    def fail(exception: BaseException) -> None:
        raise exception

    with app._command_toolbar_context():
        toolbar = app._command_toolbar

        # A UI callback runs on the display's loop, so its failure has to be carried
        # back to the command thread rather than reaching the loop's error handler.
        with pytest.raises(ValueError, match="broken ui call"):
            toolbar._call_in_ui(lambda: fail(ValueError("broken ui call")))

        # A TimeoutError raised by the callback is the same class the pending future
        # reports itself with, and must not be mistaken for one.
        with pytest.raises(TimeoutError, match="slow ui call"):
            toolbar._call_in_ui(lambda: fail(TimeoutError("slow ui call")))

        # A callback that outlives the poll interval keeps waiting instead of giving up.
        entered = threading.Event()
        release = threading.Event()

        class PendingFuture(Future):
            polled = False

            def result(self, timeout=None):
                if not self.polled:
                    self.polled = True
                    assert timeout is not None
                    assert entered.wait(5)
                    raise FutureTimeoutError
                return super().result(timeout=5)

        def finish():
            entered.set()
            assert release.wait(5)
            return "finished"

        check_running = toolbar._check_running

        def checked():
            check_running()
            release.set()

        monkeypatch.setattr(command_toolbar, "Future", PendingFuture)
        monkeypatch.setattr(toolbar, "_check_running", checked)
        try:
            assert toolbar._call_in_ui(finish) == "finished"
        finally:
            release.set()


def test_command_toolbar_ui_call_returns_a_result_that_lands_during_the_poll(toolbar_app, monkeypatch) -> None:
    """A callback finishing while the poll expires must return its value, not a timeout.

    `concurrent.futures.TimeoutError` is `TimeoutError` on Python 3.11+, so the poll
    expiring and the callback raising a timeout of its own are indistinguishable by type.
    Re-raising the caught exception once the future is done therefore reports a timeout for
    a call that actually succeeded.
    """
    app, _, _ = toolbar_app

    class RacyFuture(Future):
        """Completes, and only then reports the poll as having expired."""

        def __init__(self) -> None:
            super().__init__()
            self._polled = False

        def result(self, timeout=None):  # type: ignore[no-untyped-def]
            if timeout is not None and not self._polled:
                self._polled = True
                super().result(timeout=5)  # let the callback finish first
                raise FutureTimeoutError  # then act as though the poll had expired
            return super().result(timeout)

    monkeypatch.setattr(command_toolbar, "Future", RacyFuture)
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        assert toolbar._call_in_ui(lambda: "finished") == "finished"


def test_command_toolbar_ui_call_after_display_stopped(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        pipe.close()
        toolbar._thread.join(timeout=2)
        assert not toolbar._thread.is_alive()

        # There is no loop left to run UI work on, so asking must fail rather than
        # queue a callback onto a closed loop.
        assert toolbar.app.loop is None
        with pytest.raises(RuntimeError, match="Toolbar is not running"):
            toolbar._call_in_ui(lambda: None)


def test_command_toolbar_ui_call_reports_display_failure(toolbar_app, capsys, monkeypatch) -> None:
    app, _, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        loop = toolbar.app.loop
        schedule = loop.call_soon_threadsafe
        failed = threading.Event()

        class FailedDisplayFuture(Future):
            def result(self, timeout=None):
                assert timeout is not None
                toolbar._thread.join(5)
                assert not toolbar._thread.is_alive()
                assert not self.done()
                raise FutureTimeoutError

        monkeypatch.setattr(command_toolbar, "Future", FailedDisplayFuture)

        def die(*args, **kwargs):
            # The display dies instead of running the queued callback, so the future
            # the command is waiting on never resolves. Only drop that one request,
            # made here on the command thread. asyncio uses call_soon_threadsafe from
            # its own threads, and on Windows the default executor's join is reported
            # through it while asyncio.run() shuts the loop down. Swallowing that
            # report strands the toolbar thread for 300 seconds, or forever before
            # Python 3.12, where shutdown_default_executor() has no timeout.
            if not failed.is_set() and threading.current_thread() is threading.main_thread():
                failed.set()
                schedule(lambda: toolbar.app.exit(exception=ValueError("broken display")))
                return None
            return schedule(*args, **kwargs)

        with (
            mock.patch.object(loop, "call_soon_threadsafe", side_effect=die),
            pytest.raises(ValueError, match="broken display"),
        ):
            toolbar._call_in_ui(lambda: None)

    assert "broken display" in capsys.readouterr().err


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


def test_command_toolbar_input_eof_is_not_reported(toolbar_app, capsys) -> None:
    app, pipe, output = toolbar_app

    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        # Losing the terminal's input ends the display with EOFError. That is an
        # ordinary shutdown, not a failure the running command should hear about.
        pipe.close()
        toolbar._thread.join(timeout=2)
        assert not toolbar._thread.is_alive()
        assert toolbar._error is None

        # Output must still reach the terminal rather than a proxy nothing is draining.
        assert all(stream.proxy is None for stream in toolbar._streams)
        app.poutput("after eof")

    assert capsys.readouterr().err == ""
    assert "after eof\n" in output.getvalue()
    assert app.stdout is output
    assert app._command_toolbar is None


def test_command_toolbar_startup_failure_still_runs_the_command(toolbar_app, capsys) -> None:
    app, _, output = toolbar_app

    def broken_toolbar():
        raise ValueError("broken toolbar")

    app.main_session.bottom_toolbar = broken_toolbar
    ran = []
    # The toolbar is cosmetic. A display that cannot start must not take the command
    # with it, and must not escape cmdloop() and leave signal handlers installed.
    with app._command_toolbar_context():
        ran.append(True)
        app.poutput("command output")

    assert ran == [True]
    assert "broken toolbar" in capsys.readouterr().err
    assert "command output\n" in output.getvalue()
    assert app.stdout is output
    assert app._command_toolbar is None


def test_command_toolbar_is_not_retried_after_a_startup_failure(toolbar_app, capsys) -> None:
    app, _, _ = toolbar_app

    def broken_toolbar():
        raise ValueError("broken toolbar")

    app.main_session.bottom_toolbar = broken_toolbar
    with app._command_toolbar_context():
        pass
    assert "broken toolbar" in capsys.readouterr().err

    # Without this, every later command repeats the same failure and the same message.
    app.main_session.bottom_toolbar = "STATUS"
    with mock.patch("cmd2.command_toolbar.CommandToolbar") as toolbar, app._command_toolbar_context():
        toolbar.assert_not_called()
    assert capsys.readouterr().err == ""


def test_cmdloop_restores_signal_handlers_when_the_loop_fails(toolbar_app, monkeypatch) -> None:
    import signal

    app, _, _ = toolbar_app
    original = signal.getsignal(signal.SIGINT)
    monkeypatch.setattr(app, "_cmdloop", mock.Mock(side_effect=RuntimeError("loop failed")))

    with pytest.raises(RuntimeError, match="loop failed"):
        app.cmdloop()

    # cmd2's handlers must not outlive the loop in the host process.
    assert signal.getsignal(signal.SIGINT) is original


@pytest.mark.parametrize("enabled", [False, True])
def test_command_toolbar_headless(enabled) -> None:
    app = Cmd(allow_cli_args=False, bottom_toolbar_mode=ToolbarMode.AUTO if enabled else ToolbarMode.OFF)
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


@pytest.mark.parametrize(
    ("layout", "message"),
    [
        (Layout(Window()), "Unsupported PromptSession layout"),
        (Layout(HSplit([Window()])), "Cannot locate PromptSession bottom toolbar"),
    ],
)
def test_command_toolbar_requires_the_prompt_toolbar(toolbar_app, capsys, layout, message) -> None:
    app, _, output = toolbar_app
    # The display reuses the prompt's own toolbar container. If a future prompt-toolkit
    # release moves it, say so and keep running without a toolbar.
    with mock.patch.object(app.main_session, "layout", layout), app._command_toolbar_context():
        app.poutput("command output")
    assert message in capsys.readouterr().err
    assert app._command_toolbar is None
    assert "command output\n" in output.getvalue()
    assert app.stdout is output


def test_command_toolbar_reuses_prompt_application(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    session = app.main_session
    layout, bindings, erase = session.app.layout, session.app.key_bindings, session.app.erase_when_done
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        assert toolbar.app is session.app
        assert toolbar.toolbar is session.layout.container.children[-1]
        with app.suspend_bottom_toolbar():
            assert session.app.layout is layout
            assert session.app.key_bindings is bindings
            assert session.app.erase_when_done is erase
        assert session.app.layout is toolbar._layout
    assert session.app.layout is layout
    assert session.app.key_bindings is bindings
    assert session.app.erase_when_done is erase
    assert app._read_raw_input("Next: ", session, pre_run=lambda: pipe.send_text("answer\n")) == "answer"


@pytest.mark.parametrize("quit_key", ["q", "\x03"])
def test_builtin_pager_keeps_toolbar_live(toolbar_app, monkeypatch, quit_key) -> None:
    app, pipe, _ = toolbar_app
    app.use_builtin_pager = True
    monkeypatch.setattr(app, "stdin", Terminal())
    monkeypatch.setenv("TERM", "xterm")
    entered, refreshed, moved, found = (threading.Event() for _ in range(4))
    state = ["BEFORE"]

    def toolbar_text():
        assert threading.current_thread() is not threading.main_thread()
        if app.main_session.app.full_screen and state[0] == "AFTER":
            refreshed.set()
        return state[0]

    app.main_session.bottom_toolbar = toolbar_text
    prompt_layout = app.main_session.app.layout

    def observe(ui):
        if not ui.full_screen:
            return
        assert ui.layout.container.children[-1] is app._command_toolbar.toolbar
        entered.set()
        row = ui.layout.current_buffer.document.cursor_position_row
        if row > 0:
            moved.set()
        if row == 80:
            found.set()

    def interact():
        try:
            assert entered.wait(2)
            state[0] = "AFTER"
            assert refreshed.wait(2)
            pipe.send_text(" ")
            assert moved.wait(2)
            pipe.send_text("/row 080\n")
            assert found.wait(2)
        finally:
            pipe.send_text(quit_key)

    app.main_session.app.after_render += observe
    with mock.patch("subprocess.Popen") as external, ThreadPoolExecutor() as executor:
        interaction = executor.submit(interact)
        with app._command_toolbar_context():
            thread = app._command_toolbar._thread
            app.ppaged("\n".join(f"row {i:03d}" for i in range(100)))
            assert app._command_toolbar._thread is thread
            assert app._command_toolbar.is_active
            assert not app.main_session.app.full_screen
            assert not app.main_session.app.renderer.full_screen
        interaction.result(timeout=2)
        external.assert_not_called()
    assert app.main_session.app.layout is prompt_layout
    assert refreshed.is_set()
    assert get_typeahead(pipe) == []


def test_builtin_pager_short_output(toolbar_app, monkeypatch) -> None:
    app, _, output = toolbar_app
    app.use_builtin_pager = True
    monkeypatch.setattr(app, "stdin", Terminal())
    monkeypatch.setenv("TERM", "xterm")
    with mock.patch("subprocess.Popen") as external, app._command_toolbar_context():
        app.ppaged("short output")
        assert app._command_toolbar.is_active
        external.assert_not_called()
    assert "short output\n" in output.getvalue()


def test_builtin_pager_short_output_builds_no_pager(toolbar_app, monkeypatch) -> None:
    app, _, output = toolbar_app
    app.use_builtin_pager = True
    monkeypatch.setattr(app, "stdin", Terminal())
    monkeypatch.setenv("TERM", "xterm")
    # Output that fits is written directly, so none of the pager's widgets are needed.
    with mock.patch("cmd2.command_toolbar.Pager") as pager, app._command_toolbar_context():
        app.ppaged("short output")
        pager.assert_not_called()
    assert "short output\n" in output.getvalue()


def test_builtin_pager_needs_an_already_running_toolbar(toolbar_app, monkeypatch) -> None:
    app, _, _ = toolbar_app
    app.use_builtin_pager = True
    monkeypatch.setattr(app, "stdin", Terminal())
    monkeypatch.setenv("TERM", "xterm")
    # Outside the command loop there is no toolbar to page inside. Starting one here
    # would wrap the terminal streams and enter raw mode where the docs promise not to.
    with (
        mock.patch.object(command_toolbar.CommandToolbar, "start") as start,
        mock.patch("subprocess.Popen") as external,
    ):
        app.ppaged("row\n" * 200)
    start.assert_not_called()
    external.assert_called_once()


def test_external_pager_suspends_shared_application(toolbar_app, monkeypatch) -> None:
    app, _, _ = toolbar_app
    app.use_builtin_pager = False
    monkeypatch.setattr(app, "stdin", Terminal())
    monkeypatch.setenv("TERM", "xterm")

    def external(*args, **kwargs):
        assert not app.main_session.app.is_running
        assert app.main_session.app.layout is app.main_session.layout
        return mock.Mock()

    with mock.patch("subprocess.Popen", side_effect=external), app._command_toolbar_context():
        app.ppaged("external pager")
        assert app._command_toolbar.is_active


def test_builtin_pager_eof_restores_prompt(toolbar_app, monkeypatch) -> None:
    app, pipe, output = toolbar_app
    layout = app.main_session.app.layout

    def close_input(ui):
        if ui.full_screen:
            pipe.close()

    app.main_session.app.after_render += close_input
    original_pager = command_toolbar.Pager

    def pager(*args, **kwargs):
        instance = original_pager(*args, **kwargs)

        def expired(timeout=None):
            assert timeout is not None
            display = app._command_toolbar
            display._thread.join(5)
            assert not display._thread.is_alive()
            assert not instance.closed.is_set()
            return False

        monkeypatch.setattr(instance.closed, "wait", expired)
        return instance

    monkeypatch.setattr(command_toolbar, "Pager", pager)
    with pytest.raises(EOFError), app._command_toolbar_context():
        app._command_toolbar.page("line\n" * 100, chop=False)
    assert app.main_session.app.layout is layout
    assert not app.main_session.app.full_screen
    assert not app.main_session.app.renderer.full_screen
    assert app.stdout is output


def test_builtin_pager_does_not_capture_redirected_output(toolbar_app, monkeypatch, tmp_path) -> None:
    app, _, output = toolbar_app
    app.use_builtin_pager = True
    monkeypatch.setattr(app, "stdin", Terminal())
    monkeypatch.setenv("TERM", "xterm")
    target = tmp_path / "help.txt"
    with mock.patch("cmd2.command_toolbar.Pager") as pager, app._command_toolbar_context():
        app.onecmd_plus_hooks(f'help > "{target}"')
        pager.assert_not_called()
    assert "Cmd2 Commands" in target.read_text(encoding="utf-8")
    assert "Cmd2 Commands" not in output.getvalue()


@pytest.fixture
def expire_startup(monkeypatch):
    """Expire only this display's readiness wait, after its real render has started.

    The five-second waits are failure watchdogs, not simulated startup delays. Keep
    blocked workers alive for ownership assertions and join them before fixture teardown.
    """
    displays = []
    releases = []

    def install(app, *, block=True):
        entered = threading.Event()
        release = threading.Event()
        releases.append(release)
        original_init = command_toolbar.CommandToolbar.__init__

        def toolbar():
            entered.set()
            if block:
                assert release.wait(5), "test never released the display"
            return "STATUS"

        def init(display, *args, **kwargs):
            original_init(display, *args, **kwargs)
            displays.append(display)

            def expired(timeout=None):
                assert entered.wait(5), "display never entered its render callback"
                assert timeout is not None, "startup must bound its readiness wait"
                return False

            monkeypatch.setattr(display._ready, "wait", expired)

        app.main_session.bottom_toolbar = toolbar
        monkeypatch.setattr(command_toolbar.CommandToolbar, "__init__", init)
        if block:
            monkeypatch.setattr(command_toolbar, "_SHUTDOWN_TIMEOUT", 0.01)
        return release

    yield install
    for release in releases:
        release.set()
    for display in displays:
        if display._thread is not None:
            display._thread.join(5)
            assert not display._thread.is_alive()


def test_command_toolbar_startup_does_not_wait_forever(toolbar_app, monkeypatch, expire_startup, capsys) -> None:
    """A display that never reports itself started must not hold the command thread.

    The readiness signal comes from the display's own thread, so anything that stops it
    arriving -- a render that never completes, a frame skipped forever -- would otherwise
    block the command that is waiting to run.
    """
    app, _, _ = toolbar_app
    expire_startup(app, block=False)
    monkeypatch.setattr(command_toolbar.CommandToolbar, "_display_started", lambda *args: None)
    monkeypatch.setattr(command_toolbar.CommandToolbar, "_display_started_without_app", lambda *args: None)

    ran = []
    with app._command_toolbar_context():
        ran.append(True)

    assert ran == [True]
    assert "did not start" in capsys.readouterr().err


def test_command_toolbar_startup_timeout_does_not_block_on_cleanup(toolbar_app, expire_startup, capsys) -> None:
    """A blocked render callback must not hold the command thread through teardown either.

    The readiness wait being bounded is only half of it: the display thread is still inside
    the callback, so the join that follows has to be bounded too. This blocks the callback for
    real rather than suppressing the readiness signal, which is what the earlier test did and
    why it could not see this.
    """
    app, _, _ = toolbar_app
    blocked = expire_startup(app)

    ran = []
    try:
        started = time.monotonic()
        with app._command_toolbar_context():
            ran.append(True)
        elapsed = time.monotonic() - started

        assert ran == [True]
        # Both bounded waits, and nothing unbounded between them.
        assert elapsed < 5
        assert "did not start" in capsys.readouterr().err
    finally:
        blocked.set()


def _block_the_display(app, blocked: threading.Event) -> None:
    """Wedge the running display inside a render callback it cannot leave.

    Waits until the callback has actually been entered. Asking for a redraw only *schedules*
    one, so returning before it runs leaves a race: the pause that follows may reach the
    display's event loop first, in which case it exits cleanly and there is no wedged thread
    to test against.
    """
    entered = threading.Event()

    def blocking_toolbar() -> str:
        entered.set()
        blocked.wait(timeout=10)
        return "STATUS"

    app.main_session.bottom_toolbar = blocking_toolbar
    app._command_toolbar.app.invalidate()
    assert entered.wait(timeout=5), "the display never reached the blocking callback"


def test_command_toolbar_suspension_does_not_hand_over_a_terminal_it_still_owns(toolbar_app, monkeypatch) -> None:
    """A pause that timed out did not stop anything, and must not pretend otherwise."""
    app, _, _ = toolbar_app
    blocked = threading.Event()
    monkeypatch.setattr(command_toolbar, "_SHUTDOWN_TIMEOUT", 0.01)
    entered = []

    try:
        # The command context's own teardown fails the same way, for the same reason: the
        # display never stopped. That is the established contract for a stop that fails.
        with contextlib.suppress(RuntimeError), app._command_toolbar_context():
            display = app._command_toolbar
            assert display is not None
            _block_the_display(app, blocked)

            with pytest.raises(RuntimeError, match="did not stop"), app.suspend_bottom_toolbar():
                entered.append(True)

            # The guest never ran: the display still owns the application and the terminal.
            assert entered == []
            assert display.app.is_running is True
    finally:
        blocked.set()


def test_command_toolbar_that_would_not_stop_is_not_used_again(toolbar_app, monkeypatch) -> None:
    """The surviving thread outlives this display object, so the refusal has to as well."""
    app, _, _ = toolbar_app
    blocked = threading.Event()
    monkeypatch.setattr(command_toolbar, "_SHUTDOWN_TIMEOUT", 0.01)

    try:
        with contextlib.suppress(RuntimeError), app._command_toolbar_context():
            _block_the_display(app, blocked)
            with contextlib.suppress(RuntimeError), app.suspend_bottom_toolbar():
                pass

        assert app._command_toolbar_disabled is True

        # A later command must not start a second display over the one still running.
        with app._command_toolbar_context():
            assert app._command_toolbar is None
    finally:
        blocked.set()


def test_command_toolbar_that_would_not_stop_keeps_the_application(toolbar_app, monkeypatch) -> None:
    """Its layout and bindings are still in use; restoring them would pull them out from under it."""
    app, _, _ = toolbar_app
    blocked = threading.Event()
    monkeypatch.setattr(command_toolbar, "_SHUTDOWN_TIMEOUT", 0.01)

    try:
        with contextlib.suppress(RuntimeError), app._command_toolbar_context():
            display = app._command_toolbar
            assert display is not None
            layout = display.app.layout
            _block_the_display(app, blocked)

            with contextlib.suppress(RuntimeError), app.suspend_bottom_toolbar():
                pass

            assert display.app.layout is layout
    finally:
        blocked.set()


def test_a_surviving_display_blocks_later_handoffs(toolbar_app, expire_startup) -> None:
    """Disabling future displays is not enough: the old one still owns the terminal."""
    app, _, _ = toolbar_app
    blocked = expire_startup(app)
    entered = []

    try:
        with app._command_toolbar_context():
            pass

        # The command display is gone as an object, but its thread is not.
        assert app._command_toolbar is None
        with pytest.raises(RuntimeError, match="terminal"), app.suspend_bottom_toolbar():
            entered.append(True)
        assert entered == []
    finally:
        blocked.set()


def test_a_surviving_display_blocks_the_prompt(toolbar_app, expire_startup) -> None:
    """Two readers on one terminal is not a state to keep prompting in."""
    app, _, _ = toolbar_app
    blocked = expire_startup(app)

    try:
        with app._command_toolbar_context():
            pass

        with pytest.raises(RuntimeError, match="terminal"):
            app._read_raw_input("> ", app.main_session)
    finally:
        blocked.set()


def test_the_refusal_lifts_when_the_display_finally_exits(toolbar_app, expire_startup) -> None:
    """The thread may yet finish, and the session should not stay broken if it does.

    Lifting the refusal is not the whole of it. The pause that timed out never restored the
    application it had borrowed, so the prompt that comes next would render with the command
    display's layout and key bindings unless that teardown is finished first.
    """
    app, _, _ = toolbar_app
    blocked = expire_startup(app)

    prompt_layout = app.main_session.app.layout
    prompt_bindings = app.main_session.app.key_bindings
    prompt_erase = app.main_session.app.erase_when_done

    with app._command_toolbar_context():
        pass
    surviving = app._display_holding_terminal
    assert surviving is not None
    assert app.main_session.app.layout is not prompt_layout

    blocked.set()
    surviving._thread.join(timeout=5)

    with app.suspend_bottom_toolbar():
        pass

    assert app._display_holding_terminal is None
    assert app.main_session.app.layout is prompt_layout
    assert app.main_session.app.key_bindings is prompt_bindings
    assert app.main_session.app.erase_when_done == prompt_erase


def test_a_surviving_display_stops_another_from_starting(toolbar_app, expire_startup) -> None:
    app, _, _ = toolbar_app
    blocked = expire_startup(app)

    try:
        with app._command_toolbar_context():
            pass
        with app._command_toolbar_context():
            assert app._command_toolbar is None
    finally:
        blocked.set()


def test_installing_the_legacy_proxy_twice_keeps_the_first(toolbar_app) -> None:
    """Falling back to legacy routing on a display that already routes through a proxy must
    not replace a proxy whose worker is mid-write; the newcomer is closed instead."""
    app, _pipe, _output = toolbar_app
    with app._command_toolbar_context():
        display = app._command_toolbar
        assert display is not None
        proxy = display._proxy
        assert proxy is not None
        display._install_legacy_proxy()
        assert display._proxy is proxy
        assert all(stream.proxy is proxy for stream in display._streams)


def test_legacy_proxy_uses_the_display_session_output_without_an_ambient_session(toolbar_app) -> None:
    """The fallback can be scheduled onto the loop from a context that never entered the
    display's app session. The proxy must still resolve its output from that session -- not
    create a fresh one, which on a console-less platform raises -- so it is built with the
    session active regardless of the caller's context."""
    from prompt_toolkit.application.current import AppSession, _current_app_session

    app, _pipe, _output = toolbar_app
    with app._command_toolbar_context():
        display = app._command_toolbar
        assert display is not None
        session_output = display._app_session.output
        display._pause()  # drop the proxy so _install_legacy_proxy rebuilds it
        # Stand in a context with no display session, the way an off-loop callback would.
        token = _current_app_session.set(AppSession())
        try:
            display._install_legacy_proxy()
        finally:
            _current_app_session.reset(token)
        assert display._proxy is not None
        assert display._proxy._output is session_output


def test_restoring_the_legacy_display_on_a_stopped_display_changes_nothing(toolbar_app) -> None:
    """The fallback can be scheduled just before the display stops; by the time it runs
    there is no display to switch, and it must not install routing into a closed one."""
    app, _pipe, _output = toolbar_app
    with app._command_toolbar_context():
        display = app._command_toolbar
        assert display is not None
    layout = app.main_session.app.layout
    display._restore_legacy_display()
    assert display._proxy is None
    assert app.main_session.app.layout is layout
