"""Regression gate: one application must serve both the prompt and command execution."""

import threading
from concurrent.futures import Future

from prompt_toolkit.buffer import Buffer


def test_display_does_not_restart_between_prompt_and_command(toolbar_app) -> None:
    """Reading a line must not stop and restart the application that draws the toolbar.

    prompt-toolkit ends every Application.run() with a render whose `is_done` filter
    drops the bottom toolbar, so a run that ends between the prompt and the command
    erases the toolbar and the next run paints it again. That erase-and-repaint is the
    flicker. The fix is to never end a run there, which is what this asserts.

    This checks the run's lifecycle rather than counting rendered frames. Frame
    sampling proved unreliable in this harness: the borrowed application sometimes
    finishes early over a pipe input, producing teardown frames with no visible
    windows that are indistinguishable from a real gap.
    """
    app, pipe, _ = toolbar_app
    app.do_probe = lambda _: None
    pipe.send_text("probe\n")

    # Mirror _cmdloop: one display held open across both the prompt and the command,
    # rather than started and stopped around each command.
    with app._command_toolbar_context():
        toolbar = app._command_toolbar
        assert toolbar is not None
        run_thread = toolbar._thread
        assert toolbar.is_active

        line = app._read_command_line(app.prompt)

        assert line == "probe"
        assert toolbar.is_active, "the display stopped in order to read the line"
        assert toolbar._thread is run_thread, "the application was restarted after the prompt"

        # Entering command mode only swaps the layout, so the same run continues.
        with app._command_mode_context():
            assert toolbar.is_active
            assert toolbar._thread is run_thread, "the application was restarted for the command"
            app.onecmd_plus_hooks(line)

        # Nothing is asserted past this point: _run_cmdfinalization_hooks is decorated
        # with @suspend_toolbar, so the display is deliberately stopped and restarted
        # once per command at finalization. That boundary predates this change and is
        # a separate opportunity for the toolbar to blink.


def test_spike_accept_without_exit(toolbar_app) -> None:
    """Replacing the accept handler yields the line while the application keeps running.

    PromptSession's own accept handler calls app.exit(result=...), which is what ends
    the run and produces the toolbar-erasing is_done frame. If a replacement handler
    can hand the text to another thread instead, a single long-lived Application can
    serve both the prompt and command execution.
    """
    app, pipe, _ = toolbar_app
    session = app.main_session
    ui = session.app
    result: Future[str] = Future()
    still_running = threading.Event()

    def accept(buff: Buffer) -> bool:
        if not result.done():
            result.set_result(buff.document.text)
        # Report whether the app is still running at accept time.
        if ui.is_running and not ui.is_done:
            still_running.set()
        return True  # Keep the text; the caller resets the buffer.

    session.default_buffer.accept_handler = accept

    def drive() -> None:
        assert result.result(timeout=5) == "hello"
        # Now end the run explicitly so session.prompt() returns.
        ui.loop.call_soon_threadsafe(lambda: ui.exit(result=""))

    worker = threading.Thread(target=drive, daemon=True)
    worker.start()
    pipe.send_text("hello\n")
    session.prompt("> ")
    worker.join(timeout=5)

    assert result.done(), "accept handler never fired"
    assert still_running.is_set(), "the application had already exited at accept time"
