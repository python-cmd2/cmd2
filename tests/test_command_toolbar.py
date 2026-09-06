"""Command toolbar lifecycle and terminal integration tests."""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

import pytest
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.input.typeahead import get_typeahead
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.shortcuts import PromptSession

from cmd2 import Cmd, command_toolbar

from .conftest import RecordingOutput, Terminal


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


@pytest.mark.parametrize("builtin_pager", [False, True])
def test_command_toolbar_pipe_process_inherits_terminal(toolbar_app, tmp_path, builtin_pager) -> None:
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


def test_command_toolbar_ui_call_propagates_failures(toolbar_app) -> None:
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
        assert toolbar._call_in_ui(lambda: time.sleep(0.2) or "finished") == "finished"


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


def test_command_toolbar_ui_call_reports_display_failure(toolbar_app, capsys) -> None:
    app, _, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        loop = toolbar.app.loop
        schedule = loop.call_soon_threadsafe
        failed = threading.Event()

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


def test_builtin_pager_eof_restores_prompt(toolbar_app) -> None:
    app, pipe, output = toolbar_app
    layout = app.main_session.app.layout

    def close_input(ui):
        if ui.full_screen:
            pipe.close()

    app.main_session.app.after_render += close_input
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
    assert "Cmd2 Commands" in target.read_text()
    assert "Cmd2 Commands" not in output.getvalue()


def test_prompt_ctrl_c_raises_keyboard_interrupt(toolbar_app) -> None:
    """Ctrl-C at the main prompt aborts the line rather than returning text."""
    app, pipe, _ = toolbar_app
    pipe.send_text("partial\x03")
    with pytest.raises(KeyboardInterrupt):
        app._read_command_line(app.prompt)


def test_prompt_ctrl_d_raises_eof(toolbar_app) -> None:
    """Ctrl-D on an empty line signals end of input, which cmdloop turns into _eof."""
    app, pipe, _ = toolbar_app
    pipe.send_text("\x04")
    with pytest.raises(EOFError):
        app._read_command_line(app.prompt)


def test_accepted_line_appears_once_in_output(toolbar_app) -> None:
    """The accepted command line is committed to the terminal exactly once.

    Nothing in cmd2 prints it today: prompt-toolkit's final `is_done` frame is what
    leaves it in the scrollback. A continuous application never renders that frame,
    so this pins the behaviour that replacement code has to reproduce.
    """
    app, pipe, output = toolbar_app
    app.do_probe = lambda _: None
    pipe.send_text("probe\n")
    line = app._read_command_line(app.prompt)
    with app._command_toolbar_context():
        app.onecmd_plus_hooks(line)
    # An exact count catches both ways this can break: the line vanishing when no
    # is_done frame commits it, and it being echoed twice by a replacement for one.
    assert output.getvalue().count(f"{app.prompt}probe") == 1


def test_read_line_keeps_the_application_running(toolbar_app) -> None:
    """read_line() returns a line without ending the run that draws the toolbar."""
    app, pipe, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        pipe.send_text("hello\n")
        assert toolbar.read_line(ANSI("> ")) == "hello"
        assert toolbar.is_active, "the application stopped when the line was accepted"


def test_read_line_ctrl_c_raises_without_stopping_the_app(toolbar_app) -> None:
    """Ctrl-C aborts the line but leaves the toolbar's application running."""
    app, pipe, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        pipe.send_text("partial\x03")
        with pytest.raises(KeyboardInterrupt):
            toolbar.read_line(ANSI("> "))
        assert toolbar.is_active


def test_read_line_ctrl_d_raises_without_stopping_the_app(toolbar_app) -> None:
    """Ctrl-D on an empty line signals EOF but leaves the application running."""
    app, pipe, _ = toolbar_app
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        pipe.send_text("\x04")
        with pytest.raises(EOFError):
            toolbar.read_line(ANSI("> "))
        assert toolbar.is_active
