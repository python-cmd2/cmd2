"""Regression gate: the bottom toolbar must never be absent from a rendered frame."""

import threading
from concurrent.futures import Future

from prompt_toolkit.buffer import Buffer


def _toolbar_window(app):
    """Return the Window inside the PromptSession's bottom-toolbar container."""
    return app.main_session.layout.container.children[-1].content


def test_no_toolbar_gap_between_prompt_and_command(toolbar_app) -> None:
    """Pressing Enter must not erase the toolbar while the command display starts.

    prompt-toolkit ends every Application.run() with a render whose `is_done` filter
    drops the toolbar. Crossing that boundary once per command is what makes the
    toolbar blink, so no frame drawn across the handoff may omit it.
    """
    app, pipe, _ = toolbar_app
    ui = app.main_session.app
    toolbar_window = _toolbar_window(app)
    missing: list[bool] = []

    def record(rendered_app) -> None:
        # visible_windows survives Renderer.reset(), which nulls _last_screen on the
        # is_done frame. Reading the screen instead reports every done frame as empty.
        missing.append(toolbar_window not in rendered_app.layout.visible_windows)

    ui.after_render += record
    app.do_probe = lambda _: None
    try:
        pipe.send_text("probe\n")
        # Mirror _cmdloop: one display held open across both the prompt and the
        # command, rather than started and stopped around each command.
        with app._command_toolbar_context():
            line = app._read_command_line(app.prompt)
            with app._command_mode_context():
                app.onecmd_plus_hooks(line)
    finally:
        ui.after_render.remove_handler(record)

    assert missing, "no frames were recorded; the probe did not run"
    assert not any(missing), f"{sum(missing)} of {len(missing)} frames had no bottom toolbar"


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
