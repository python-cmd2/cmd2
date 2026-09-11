"""Reservation boundaries interpreted by a terminal, rather than a fixed row-one CPR stub."""

import io
import sys
import threading
from types import SimpleNamespace

import pyte
import pytest

from cmd2.reserved_toolbar import ReservedToolbar
from cmd2.utils import StdSim

from .test_reserved_lifecycle import Harness


class TerminalScreen(pyte.HistoryScreen):
    """Keep DECRC's physical position even when it is outside the scroll margins.

    pyte 0.8.2 unconditionally clamps a restored cursor to the margins. iTerm2 and
    tmux retain the physical row when origin mode is off; that distinction is the
    bug these tests exercise. Let pyte restore against the whole screen in that mode.
    """

    def restore_cursor(self) -> None:
        margins = self.margins
        if self.savepoints and not self.savepoints[-1].origin:
            self.margins = None
        try:
            super().restore_cursor()
        finally:
            self.margins = margins


class EmulatedTerminal(io.StringIO):
    """Parse output and answer CPR where the cursor actually is when the query arrives."""

    def __init__(self, rows, reply) -> None:
        super().__init__()
        self.screen = TerminalScreen(80, rows, history=1000)
        self.reports = []

        def respond(data):
            self.reports.append(self.screen.cursor.y + 1)
            reply(data)

        self.screen.write_process_input = respond
        self.parser = pyte.Stream(self.screen)
        self.buffer = SimpleNamespace(write=lambda data: self.write(data.decode("utf-8")))

    def write(self, data):
        count = super().write(data)
        # The tty's output processing supplies carriage returns to subprocess newlines.
        self.parser.feed(data.replace("\n", "\r\n"))
        return count

    def isatty(self) -> bool:
        return True


@pytest.fixture
def terminal_harness(request):
    rows = getattr(request, "param", 24)
    harness = Harness(rows=rows)
    stream = EmulatedTerminal(rows, harness.pipe.send_text)
    harness.stream = stream
    harness.backend.stdout = stream
    harness.app.stdout = stream
    try:
        yield harness, stream
    finally:
        harness.close()


def read_prompt(harness, terminal, expected_toolbar="STATUS") -> None:
    """Use the real input reader and CPR binding, then accept a prompt with known height."""
    ui = harness.app.main_session.app
    sent = False

    def ready(app):
        nonlocal sent
        if not sent and app.renderer._min_available_height > 0:
            sent = True
            harness.pipe.send_text("next\n")

    ui.after_render += ready
    watchdog = threading.Timer(5, harness.pipe.close)
    watchdog.daemon = True
    watchdog.start()
    try:
        assert harness.app._read_raw_input("TEST> ", harness.app.main_session) == "next"
        assert sent
        assert terminal.reports
        assert all(row < terminal.screen.lines for row in terminal.reports)
        assert terminal.screen.display[-1].startswith(expected_toolbar)
    finally:
        watchdog.cancel()
        watchdog.join()
        ui.after_render -= ready


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("STATUS\nsecond line", "STATUS" + " " * 73 + "…"),
        ("\nSTATUS", " " * 79 + "…"),
        ("S" * 81, "S" * 79 + "…"),
        ("S" * 78 + "广x", "S" * 78 + " …"),
    ],
)
def test_clipped_toolbar_survives_commands_and_prompt_refresh(terminal_harness, content, expected) -> None:
    harness, terminal = terminal_harness
    harness.app.main_session.bottom_toolbar = content
    with harness.app._reserved_toolbar_context():
        assert terminal.screen.display[-1] == expected
        with harness.app._command_toolbar_context():
            harness.app.poutput("ordinary output")
        assert terminal.screen.display[-1] == expected
        read_prompt(harness, terminal, expected_toolbar=expected)
        # A shorter dynamic replacement must remove the old text and indicator.
        harness.app.main_session.bottom_toolbar = "OK"
        assert harness.app.reserved_toolbar.refresh()
        assert terminal.screen.display[-1] == "OK" + " " * 78
    assert terminal.screen.margins is None
    assert terminal.screen.display[-1].strip() == ""


@pytest.mark.parametrize("row", [1, 22, 23, 24])
@pytest.mark.parametrize("reserved", [1, 2])
def test_acquisition_keeps_existing_output_and_cursor_above_the_band(terminal_harness, row, reserved) -> None:
    harness, terminal = terminal_harness
    terminal.write(f"\x1b[{row};1Hexisting output")
    with ReservedToolbar(harness.app.main_session, lambda: "STATUS", reserved_rows=reserved):
        expected_row = min(row, 24 - reserved)
        assert terminal.screen.cursor.y + 1 == expected_row
        assert terminal.screen.cursor.x == len("existing output")
        assert terminal.screen.display[expected_row - 1].startswith("existing output")
        assert terminal.screen.display[24 - reserved].startswith("STATUS")
    assert terminal.screen.margins is None


@pytest.mark.parametrize("terminal_harness", [12, 24, 40], indirect=True)
def test_a_prompt_started_on_the_bottom_row_gets_a_usable_cursor_report(terminal_harness, capsys) -> None:
    harness, terminal = terminal_harness
    terminal.write(f"\x1b[{terminal.screen.lines};1H")
    with harness.app._reserved_toolbar_context():
        # Fail before trying input if startup has left the cursor in the band.
        assert terminal.screen.cursor.y < terminal.screen.lines - 1
        read_prompt(harness, terminal)
    assert "doesn't support cursor position requests" not in capsys.readouterr().err
    assert terminal.screen.margins is None


@pytest.mark.parametrize("terminal_harness", [12, 24, 40], indirect=True)
def test_shell_output_scrolling_to_the_bottom_returns_a_working_prompt(terminal_harness, capfd) -> None:
    harness, terminal = terminal_harness
    # Exercise a real shell subprocess and ProcReader, echoing its captured bytes to
    # the same terminal as the toolbar. This supplies a real pipe rather than fileno()
    # on the in-memory terminal.
    harness.app.stdout = StdSim(terminal, echo=True)
    with harness.app._reserved_toolbar_context():
        command = f"!\"{sys.executable}\" -S -c \"print('out\\n' * 80, end='')\""
        harness.app.onecmd_plus_hooks(command)
        assert harness.app.last_result == 0
        assert terminal.screen.cursor.y == terminal.screen.lines - 2
        assert terminal.screen.display[-3].rstrip() == "out"
        assert terminal.screen.display[-1].startswith("STATUS")
        # Every emitted line must remain in the viewport or scrollback exactly once.
        history = ["".join(line[x].data for x in sorted(line)) for line in terminal.screen.history.top]
        assert sum(line.rstrip() == "out" for line in history + terminal.screen.display) == 80
        read_prompt(harness, terminal)
    assert "doesn't support cursor position requests" not in capfd.readouterr().err
    assert terminal.screen.margins is None


def test_release_does_not_erase_rows_from_a_changed_viewport(terminal_harness) -> None:
    harness, terminal = terminal_harness
    with harness.app._reserved_toolbar_context():
        # The reserved row was cropped by a resize; the new bottom row is application
        # output. CUP to the old row would clamp there and erase somebody else's text.
        terminal.screen.resize(lines=12, columns=80)
        harness.size = type(harness.size)(rows=12, columns=80)
        terminal.write("\x1b[12;1Hkeep this output")
    assert terminal.screen.display[-1].startswith("keep this output")
    assert terminal.screen.margins is None


def test_release_still_resets_margins_when_geometry_cannot_be_measured(terminal_harness, monkeypatch) -> None:
    harness, terminal = terminal_harness
    with harness.app._reserved_toolbar_context():

        def unavailable():
            raise OSError("terminal size unavailable")

        monkeypatch.setattr(harness.backend, "get_size", unavailable)
    assert terminal.screen.margins is None
