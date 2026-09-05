"""Command toolbar lifecycle and terminal integration tests."""

import io
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

import pytest
from prompt_toolkit.application import create_app_session, get_app
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.input.typeahead import get_typeahead
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.shortcuts import PromptSession

from cmd2 import Cmd
from cmd2.pager import Pager


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


class RecordingOutput(DummyOutput):
    def __init__(self, stream: Terminal) -> None:
        self.stdout = stream
        self.size = Size(rows=24, columns=80)

    def get_size(self) -> Size:
        return self.size

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

        def die(*_args, **_kwargs) -> None:
            # The display dies instead of running the queued callback, so the future
            # the command is waiting on never resolves.
            if not failed.is_set():
                failed.set()
                schedule(lambda: toolbar.app.exit(exception=ValueError("broken display")))

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


def test_command_toolbar_render_failure(toolbar_app) -> None:
    app, _, output = toolbar_app

    def broken_toolbar():
        raise ValueError("broken toolbar")

    app.main_session.bottom_toolbar = broken_toolbar
    with pytest.raises(ValueError, match="broken toolbar"), app._command_toolbar_context():
        pytest.fail("Command should not run after a toolbar startup failure")  # pragma: no cover
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


@pytest.mark.parametrize(
    ("layout", "error", "message"),
    [
        (Layout(Window()), TypeError, "Unsupported PromptSession layout"),
        (Layout(HSplit([Window()])), RuntimeError, "Cannot locate PromptSession bottom toolbar"),
    ],
)
def test_command_toolbar_requires_the_prompt_toolbar(toolbar_app, layout, error, message) -> None:
    app, _, output = toolbar_app
    # The display reuses the prompt's own toolbar container. If a future prompt-toolkit
    # release moves it, say so instead of rendering something wrong.
    with mock.patch.object(app.main_session, "layout", layout), pytest.raises(error, match=message):
        app._command_toolbar_context().__enter__()
    assert app._command_toolbar is None
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


@pytest.mark.parametrize("chop", [False, True])
def test_pager_styles_and_wrapping(chop) -> None:
    pager = Pager("\x1b[31m" + "界" * 40 + "\x1b[0m\n", chop=chop)
    assert pager.text.text == "界" * 40
    assert pager.text.read_only
    lexer = pager.text.lexer.lex_document(pager.text.document)
    assert "ansired" in lexer(0)[0][0]
    assert not pager.fits(20, 1)
    assert pager.fits(20, 5) is (not chop)
    assert pager.fits(100, 1)


@pytest.mark.parametrize("chop", [False, True])
def test_pager_long_line_navigation_resize_and_typeahead(toolbar_app, chop) -> None:
    app, pipe, _ = toolbar_app
    app.main_session.bottom_toolbar = "STATUS ONE\nSTATUS TWO"
    entered, scrolled, resized = (threading.Event() for _ in range(3))

    def observe(ui):
        if not ui.full_screen:
            return
        # Check the rendered frame, not the stream of incremental terminal
        # writes, to verify both toolbar rows survive navigation and resizing.
        screen = ui.renderer._last_screen
        size = ui.output.get_size()
        bottom = "".join(screen.data_buffer[size.rows - 1][x].char for x in range(size.columns))
        assert bottom.startswith("STATUS TWO")
        entered.set()
        if ui.current_buffer.cursor_position > 0:
            scrolled.set()
        if size.columns == 60:
            resized.set()

    def interact():
        try:
            assert entered.wait(2)
            pipe.send_text("\x1b[C" if chop else " ")
            assert scrolled.wait(2)
            app.main_session.output.size = Size(rows=20, columns=60)
            app.main_session.app.invalidate()
            assert resized.wait(2)
        finally:
            pipe.send_text("qnext\n")

    app.main_session.app.after_render += observe
    with ThreadPoolExecutor() as executor:
        interaction = executor.submit(interact)
        with app._command_toolbar_context():
            app._command_toolbar.page("界" * 4000, chop=chop)
        interaction.result(timeout=2)
    assert app._read_raw_input("Next: ", app.main_session) == "next"


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


class PagerKeys:
    """Send keys to the built-in pager and wait for each one to be handled."""

    def __init__(self, app, pipe, pager) -> None:
        self.pipe = pipe
        self.pager = pager
        self.states = []
        self.updated = threading.Condition()
        app.main_session.app.key_processor.after_key_press += self._record

    def _record(self, _) -> None:
        # Read the pager's own buffer rather than the focused one, which is the
        # search field while a search is being typed.
        with self.updated:
            self.states.append((self.pager.text.buffer.document.cursor_position_row, self.pager.text.window.horizontal_scroll))
            self.updated.notify_all()

    def press(self, keys, row, column=0) -> None:
        """Send keys and wait until a resulting position matches, so steps stay ordered."""
        with self.updated:
            index = len(self.states)
        self.pipe.send_text(keys)
        deadline = time.monotonic() + 5
        with self.updated:
            while True:
                while index < len(self.states):
                    state = self.states[index]
                    index += 1
                    if state == (row, column):
                        return
                remaining = deadline - time.monotonic()
                notified = remaining > 0 and self.updated.wait(remaining)
                assert notified, f"pager ignored {keys!r}: wanted {(row, column)}, saw {self.states}"


@pytest.mark.parametrize("chop", [False, True])
def test_pager_navigation_keys(toolbar_app, chop) -> None:
    app, pipe, _ = toolbar_app
    lines = [f"row {index:03d}" for index in range(100)]
    lines[3] = ""  # A line with no columns for a scroll target to be clamped against.
    created = []
    entered = threading.Event()

    def make_pager(*args, **kwargs):
        pager = Pager(*args, **kwargs)
        created.append(pager)
        return pager

    def observe(ui):
        if created and ui.full_screen and ui.layout.current_buffer is created[0].text.buffer:
            entered.set()

    def interact():
        try:
            assert entered.wait(5)
            keys = PagerKeys(app, pipe, created[0])
            keys.press("j", row=1)
            keys.press("j", row=2)
            keys.press("j", row=3)  # Land on the empty line.
            keys.press("k", row=2)  # Moving up off it re-enters the line above.
            keys.press("G", row=99)
            keys.press("g", row=0)
            keys.press("/row 05\n", row=50)
            keys.press("n", row=51)
            keys.press("N", row=50)
            keys.press("?row 01\n", row=19)
            keys.press("x", row=19)  # Unbound keys are swallowed, not queued for the prompt.
            # Horizontal scrolling applies only to chopped output, and stops at the
            # end of a line shorter than the requested column.
            keys.press("\x1b[C", row=19, column=len("row 019") if chop else 0)
            keys.press("\x1b[D", row=19, column=0)
        finally:
            pipe.send_text("q")

    app.main_session.app.after_render += observe
    with mock.patch("cmd2.command_toolbar.Pager", side_effect=make_pager), ThreadPoolExecutor() as executor:
        interaction = executor.submit(interact)
        with app._command_toolbar_context():
            app._command_toolbar.page("\n".join(lines), chop=chop)
        interaction.result(timeout=10)
    assert get_typeahead(pipe) == []


@pytest.mark.parametrize("chop", [False, True])
def test_pager_scrolling_before_first_render(chop) -> None:
    pager = Pager("row\n" * 100, chop=chop)
    # Keys can arrive before the first frame is drawn, when the window still has no
    # rendered geometry to scroll against.
    assert pager.text.window.render_info is None
    event = SimpleNamespace(current_buffer=pager.text.buffer)
    pager._scroll_page(event, pages=1.0)
    pager._scroll(event, 1)
    pager._scroll_horizontal(event, 1)
    assert pager.text.buffer.cursor_position == 0
    assert pager.text.window.horizontal_scroll == 0
