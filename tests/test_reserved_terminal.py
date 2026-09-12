"""Reservation boundaries interpreted by a terminal, rather than a fixed row-one CPR stub."""

import io
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pyte
import pytest
from prompt_toolkit.data_structures import Size

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


def wait_for(predicate, timeout: float = 5.0) -> bool:
    """Poll until the display thread has done something observable, or give up."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def committed_frames(harness) -> list[int]:
    """Count frames the bridge actually committed; upstream's event fires only for those."""
    count = [0]

    def bump(app) -> None:
        count[0] += 1

    harness.app.main_session.app.after_render += bump
    return count


def resize(harness, terminal, rows: int, columns: int) -> None:
    """Resize the emulated terminal the way a real one is resized: all at once, margins reset."""
    terminal.screen.resize(lines=rows, columns=columns)
    terminal.screen.set_margins()
    harness.size = Size(rows=rows, columns=columns)


class TestResize:
    """A resize during a command reaches the display only through prompt-toolkit's size poll.

    The command display runs on its own thread, where no window-change signal can be
    attached, so the poll on ``output.get_size()`` is the only way a resize arrives there.
    """

    @pytest.mark.parametrize(("rows", "columns"), [(12, 40), (40, 100)])
    def test_a_resize_during_a_command_reinstalls_the_region_and_repaints(self, terminal_harness, rows, columns) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            ui = harness.app._command_toolbar.app
            resize(harness, terminal, rows, columns)
            # A resize during a command reaches the display through prompt-toolkit's size poll,
            # which reads the adapter -- now reporting the true physical height (see
            # test_the_virtual_size_follows_a_resize) -- and calls _on_resize. Drive that
            # handler once, deterministically, rather than racing the async poll's interval.
            ui.loop.call_soon_threadsafe(ui._on_resize)
            assert wait_for(lambda: terminal.screen.margins == pyte.screens.Margins(0, rows - 2))
            assert ui.output.get_size() == Size(rows=rows - 1, columns=columns)
            assert wait_for(lambda: terminal.screen.display[-1].startswith("STATUS"))
            assert harness.app.reserved_toolbar.display.geometry.physical_size == Size(rows=rows, columns=columns)
            # The band moved, so the old one must not linger as a second toolbar.
            assert sum(row.startswith("STATUS") for row in terminal.screen.display) == 1
            harness.app.poutput("after")
            assert terminal.screen.display[-1].startswith("STATUS")
        assert terminal.screen.margins is None

    def test_a_resize_at_the_prompt_reinstalls_the_region_and_keeps_the_prompt_usable(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        ui = harness.app.main_session.app
        resized = False

        def on_render(app) -> None:
            nonlocal resized
            if not resized:
                resized = True
                resize(harness, terminal, 12, 40)
                # At the prompt the signal handler is what fires; deliver what it would.
                ui.loop.call_soon_threadsafe(ui._on_resize)

        ui.after_render += on_render
        try:
            with harness.app._reserved_toolbar_context():
                read_prompt(harness, terminal)
                assert terminal.screen.margins == pyte.screens.Margins(0, 10)
                assert ui.output.get_size() == Size(rows=11, columns=40)
                assert terminal.screen.display[-1].startswith("STATUS")
                assert any(row.startswith("TEST> next") for row in terminal.screen.display)
        finally:
            ui.after_render -= on_render
        assert terminal.screen.margins is None


class TestPartialLines:
    """Output that ends without a newline is a line in progress, not a line to redraw over."""

    def _write_partial_and_redraw(self, harness, terminal, text: str) -> None:
        frames = committed_frames(harness)
        before = frames[0]
        harness.app.stdout.write(text)
        harness.app.stdout.flush()
        harness.app._command_toolbar.app.invalidate()
        assert wait_for(lambda: frames[0] > before)
        bridge = harness.app.reserved_toolbar.bridge
        assert wait_for(lambda: not bridge.needs_resynchronization and bridge.in_flight is None)

    def test_partial_output_survives_the_redraw_and_the_next_write_continues_it(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            self._write_partial_and_redraw(harness, terminal, "PARTIAL")
            assert terminal.screen.display[0].startswith("PARTIAL")
            assert (terminal.screen.cursor.x, terminal.screen.cursor.y) == (len("PARTIAL"), 0)
            harness.app.stdout.write("END\n")
            harness.app.stdout.flush()
            assert terminal.screen.display[0].startswith("PARTIALEND")
            assert terminal.screen.display[-1].startswith("STATUS")

    def test_partial_output_on_the_last_usable_row_survives_too(self, terminal_harness) -> None:
        """A whole-line delete there has nothing below it to delete, and takes the line itself."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            usable = terminal.screen.lines - 1
            harness.app.stdout.write("out\n" * (usable - 1))
            harness.app.stdout.flush()
            self._write_partial_and_redraw(harness, terminal, "PARTIAL")
            assert terminal.screen.cursor.y + 1 == usable
            assert terminal.screen.display[usable - 1].startswith("PARTIAL")
            harness.app.stdout.write("END\n")
            harness.app.stdout.flush()
            assert terminal.screen.display[usable - 2].startswith("PARTIALEND")
            assert terminal.screen.display[-1].startswith("STATUS")

    def test_partial_output_survives_the_command_display_shutdown(self, terminal_harness) -> None:
        """Leaving the command context stops the empty display, whose shutdown must not erase
        the command output still on the line."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context():
            with harness.app._command_toolbar_context():
                harness.app.stdout.write("PARTIAL")
                harness.app.stdout.flush()
            assert terminal.screen.display[0].startswith("PARTIAL")
            assert terminal.screen.display[-1].startswith("STATUS")

    def test_a_carriage_return_progress_line_ends_on_its_final_value(self, terminal_harness) -> None:
        """A \r-updated progress line is a sequence of partial writes; each must survive its redraw."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            self._write_partial_and_redraw(harness, terminal, "Progress: 0%")
            assert terminal.screen.display[0].startswith("Progress: 0%")
            self._write_partial_and_redraw(harness, terminal, "\rProgress: 50%")
            assert terminal.screen.display[0].startswith("Progress: 50%")
            harness.app.stdout.write("\rProgress: 100%\n")
            harness.app.stdout.flush()
            assert terminal.screen.display[0].startswith("Progress: 100%")
            assert terminal.screen.display[-1].startswith("STATUS")


class TestPager:
    """The built-in pager renders a full screen of its own, so its frames must not be
    suppressed the way an ordinary command's empty frames are."""

    def test_the_pager_draws_its_content_over_the_reserved_toolbar(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            display = harness.app._command_toolbar
            body = "\n".join(f"row {index:03d}" for index in range(200))
            shown = threading.Event()

            def drive() -> None:
                # Wait until the pager has painted its first screen, then quit it. Quit either
                # way, so a pager that never draws fails the assertion instead of hanging the
                # blocking page() call forever.
                try:
                    if wait_for(lambda: terminal.screen.display[0].startswith("row 000")):
                        shown.set()
                finally:
                    harness.pipe.send_text("q")

            with ThreadPoolExecutor() as executor:
                future = executor.submit(drive)
                display.page(body, chop=False)
                future.result(timeout=5)

            assert shown.is_set(), "the pager never drew its content"
            # The toolbar is suppressed again for ordinary output once the pager has closed.
            assert harness.app.reserved_toolbar.bridge._render_suppressed is True
        assert terminal.screen.margins is None

    def test_output_that_fits_is_printed_without_a_pager(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            harness.app._command_toolbar.page("one short line", chop=False)
            assert any(row.startswith("one short line") for row in terminal.screen.display)
            assert terminal.screen.display[-1].startswith("STATUS")
