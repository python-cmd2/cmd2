"""Reservation boundaries interpreted by a terminal, rather than a fixed row-one CPR stub."""

import asyncio
import io
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pyte
import pytest
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.data_structures import Size

from cmd2 import command_toolbar
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

    def resize(self, lines: int | None = None, columns: int | None = None) -> None:
        """Shrink by clipping the bottom while the cursor stays on screen.

        pyte clips from the top, inside the scroll margins, which drops the cursor's own
        line. xterm and VTE keep the cursor's line visible: with the cursor above the new
        bottom they clip the rows below it, which is the case these tests exercise. The
        band's old row goes with those rows, as it does on a real terminal.
        """
        lines = lines or self.lines
        if lines < self.lines and self.cursor.y < lines:
            for y in range(lines, self.lines):
                self.buffer.pop(y, None)
            self.lines = lines
            self.dirty.update(range(lines))
            self.set_margins()
        super().resize(lines=lines, columns=columns)


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


def test_background_output_survives_return_to_active_prompt(terminal_harness) -> None:
    harness, terminal = terminal_harness
    ui = harness.app.main_session.app
    started = False
    finished = False
    sent = False
    task = None

    async def output():
        nonlocal finished
        await run_in_terminal(lambda: terminal.write("BACKGROUND MESSAGE\n"))
        finished = True
        ui.invalidate()

    def ready(app):
        nonlocal started, sent, task
        if not started and app.renderer._min_available_height > 0:
            started = True
            task = app.create_background_task(output())
        elif finished and not sent and app.renderer._min_available_height > 0:
            sent = True
            harness.pipe.send_text("next\n")

    ui.after_render += ready
    watchdog = threading.Timer(5, harness.pipe.close)
    watchdog.start()
    try:
        with harness.app._reserved_toolbar_context():
            assert harness.app._read_raw_input("TEST> ", harness.app.main_session) == "next"
            assert task is not None
            assert task.done()
            task.result()
            assert sum("BACKGROUND MESSAGE" in row for row in terminal.screen.display) == 1
            assert any(row.startswith("TEST> next") for row in terminal.screen.display)
            assert terminal.screen.display[-1].startswith("STATUS")
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

    @pytest.mark.parametrize("terminal_harness", [2], indirect=True)
    def test_initially_short_prompt_grows_and_accepts_visible_input(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        ui = harness.app.main_session.app
        resized = False
        sent = False

        def ready(app):
            nonlocal resized, sent
            if not resized:
                resized = True
                resize(harness, terminal, 24, 80)
                ui.loop.call_soon_threadsafe(ui._on_resize)
            elif not sent and harness.app.reserved_toolbar.is_active:
                sent = True
                harness.pipe.send_text("next\n")

        ui.after_render += ready
        watchdog = threading.Timer(5, harness.pipe.close)
        watchdog.start()
        try:
            with harness.app._reserved_toolbar_context():
                assert harness.app._read_raw_input("TEST> ", harness.app.main_session) == "next"
                assert any(row.startswith("TEST> next") for row in terminal.screen.display)
                assert terminal.screen.display[-1].startswith("STATUS")
        finally:
            watchdog.cancel()
            watchdog.join()
            ui.after_render -= ready

    @pytest.mark.parametrize("terminal_harness", [2], indirect=True)
    def test_initially_short_terminal_acquires_during_a_quiet_command(self, terminal_harness, monkeypatch) -> None:
        harness, terminal = terminal_harness
        # Exercise the actual size poll, without explicitly invalidating or calling _on_resize.
        harness.app.main_session.app.terminal_size_polling_interval = 0.01
        with harness.app._reserved_toolbar_context():
            toolbar = harness.app.reserved_toolbar
            assert not toolbar.is_active
            output = harness.app.main_session.app.output
            get_size = output.get_size
            polled = threading.Event()

            def observe_size():
                size = get_size()
                try:
                    task = asyncio.current_task()
                except RuntimeError:
                    task = None
                # Identified by the name of prompt-toolkit's own polling coroutine,
                # Application._poll_output_size in the qualified 3.0.53. It is upstream
                # internal, so this is one of the places a version bump has to revisit.
                if task is not None and task.get_coro().__name__ == "_poll_output_size":
                    polled.set()
                return size

            monkeypatch.setattr(output, "get_size", observe_size)
            with harness.app._command_toolbar_context():
                # The upstream poll first establishes a baseline; resize after it has
                # sampled the short terminal, rather than racing its initial sample.
                assert polled.wait(5)
                resize(harness, terminal, 24, 80)
                assert wait_for(lambda: toolbar.is_active)
                assert output.get_size() == Size(rows=23, columns=80)
                assert wait_for(lambda: terminal.screen.display[-1].startswith("STATUS"))
                harness.app.stdout.write("PARTIAL")
                harness.app.stdout.flush()
        assert any(row.startswith("PARTIAL") for row in terminal.screen.display)
        assert terminal.screen.margins is None

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

    @pytest.mark.parametrize("lines", [0, 22])
    def test_partial_output_survives_the_next_main_prompt(self, terminal_harness, lines) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context():
            with harness.app._command_toolbar_context():
                harness.app.stdout.write("out\n" * lines + "IMPORTANT PARTIAL")
                harness.app.stdout.flush()
            read_prompt(harness, terminal)
            history = ["".join(line[x].data for x in sorted(line)) for line in terminal.screen.history.top]
            visible = history + terminal.screen.display
            assert sum("IMPORTANT PARTIAL" in row for row in visible) == 1
            assert any("TEST> next" in row for row in visible)

    def test_a_handoff_forgets_unfinished_output_so_the_prompt_is_not_pushed_down(self, terminal_harness) -> None:
        """A partial write followed by a guest that finishes the line: the guest moved the
        cursor to a fresh line, so the prompt must not add another one on the strength of a
        verdict about output the guest has since completed."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context():
            with harness.app._command_toolbar_context():
                harness.app.stdout.write("PARTIAL")
                harness.app.stdout.flush()
                with harness.app.suspend_bottom_toolbar():
                    harness.app.stdout.write("done\n")
                    harness.app.stdout.flush()
            read_prompt(harness, terminal)
            assert terminal.screen.display[0].startswith("PARTIALdone")
            assert terminal.screen.display[1].startswith("TEST> next")

    def test_guest_partial_output_survives_command_resume(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            with harness.app.suspend_bottom_toolbar():
                harness.app.stdout.write("PARTIAL")
                harness.app.stdout.flush()
            frames = committed_frames(harness)
            harness.app._command_toolbar.app.invalidate()
            assert wait_for(lambda: frames[0] > 0)
            assert wait_for(lambda: not harness.app.reserved_toolbar.bridge.needs_resynchronization)
            assert terminal.screen.cursor.x == 7
            harness.app.stdout.write("END\n")
            harness.app.stdout.flush()
            assert terminal.screen.display[0].startswith("PARTIALEND")

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

    def test_partial_output_survives_a_resize(self, terminal_harness) -> None:
        """A resize during a command reflows the region but must not erase a line in progress;
        the next write continues it."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            ui = harness.app._command_toolbar.app
            harness.app.stdout.write("PARTIAL")
            harness.app.stdout.flush()
            resize(harness, terminal, 12, 80)
            ui.loop.call_soon_threadsafe(ui._on_resize)
            assert wait_for(lambda: terminal.screen.margins == pyte.screens.Margins(0, 10))
            harness.app.stdout.write("END\n")
            harness.app.stdout.flush()
            assert terminal.screen.display[0].startswith("PARTIALEND")
            assert terminal.screen.display[-1].startswith("STATUS")

    def test_partial_output_on_a_row_the_shrunk_band_takes_moves_up_with_its_cursor(self, terminal_harness) -> None:
        """Shrinking can leave the cursor's row inside the new band. The output there and the
        cursor move up into the usable region, column intact, before the band is painted."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            ui = harness.app._command_toolbar.app
            harness.app.stdout.write("out\n" * 11 + "PARTIAL")
            harness.app.stdout.flush()
            assert (terminal.screen.cursor.x, terminal.screen.cursor.y + 1) == (len("PARTIAL"), 12)
            resize(harness, terminal, 12, 80)
            ui.loop.call_soon_threadsafe(ui._on_resize)
            assert wait_for(lambda: terminal.screen.margins == pyte.screens.Margins(0, 10))
            assert wait_for(lambda: terminal.screen.display[-1].startswith("STATUS"))
            # Row 12 is the band now; the line and its cursor were scrolled up to row 11.
            assert (terminal.screen.cursor.x, terminal.screen.cursor.y + 1) == (len("PARTIAL"), 11)
            assert terminal.screen.display[10].startswith("PARTIAL")
            harness.app.stdout.write("END\n")
            harness.app.stdout.flush()
            # The newline at the bottom of the usable region scrolls it, so the finished line
            # sits one row up; it must be complete, and nothing may have landed in the band.
            usable = terminal.screen.display[:-1]
            assert any(row.startswith("PARTIALEND") for row in usable)
            assert terminal.screen.display[-1].startswith("STATUS")
            assert "END" not in terminal.screen.display[-1]
            assert sum(row.startswith("STATUS") for row in terminal.screen.display) == 1

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


PAGER_BODY = "\n".join(f"row {index:03d}" for index in range(200))


def run_pager(harness, terminal, while_open=None) -> bool:
    """Page a body taller than the screen on the command display, then quit the pager.

    ``while_open`` runs on the driving thread once the pager has painted its first screen.
    The quit key is sent either way, so a pager that never draws fails the caller's
    assertion instead of hanging the blocking ``page()`` call forever.

    :return: whether the pager drew its first screen
    """
    display = harness.app._command_toolbar
    shown = threading.Event()
    created: list[Any] = []
    real_pager = command_toolbar.Pager

    def make_pager(*args: Any, **kwargs: Any) -> Any:
        pager = real_pager(*args, **kwargs)
        created.append(pager)
        return pager

    def drive() -> None:
        try:
            if wait_for(lambda: terminal.screen.display[0].startswith("row 000")):
                shown.set()
                if while_open is not None:
                    while_open()
        finally:
            harness.pipe.send_text("q")
            # A pager that no longer answers its quit key -- its layout swapped out from
            # under it, say -- would leave page() blocked forever. Close it by hand so the
            # test fails on the assertion instead of hanging.
            if created and not wait_for(created[0].closed.is_set, timeout=3):
                created[0].closed.set()
                raise AssertionError("the pager did not close on its quit key")

    with mock.patch.object(command_toolbar, "Pager", make_pager), ThreadPoolExecutor() as executor:
        future = executor.submit(drive)
        display.page(PAGER_BODY, chop=False)
        future.result(timeout=5)
    return shown.is_set()


class TestPager:
    """The built-in pager renders a full screen of its own, so its frames must not be
    suppressed the way an ordinary command's empty frames are."""

    def test_abandoning_reservation_restores_legacy_display_and_routing(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            reserved = harness.app.reserved_toolbar
            display = harness.app._command_toolbar

            class BrokenContent:
                def __pt_formatted_text__(self):
                    raise ValueError("cannot format toolbar")

            reserved.content = BrokenContent

            def fail():
                reserved.refresh()
                reserved.refresh()

            display.app.loop.call_soon_threadsafe(fail)
            assert wait_for(lambda: not reserved.is_active)
            assert wait_for(lambda: display._proxy is not None)
            assert all(stream.serializer is None for stream in display._streams)
            harness.app.main_session.bottom_toolbar = "RECOVERED"
            display.app.invalidate()
            assert wait_for(lambda: terminal.screen.display[-1].startswith("RECOVERED"))
            harness.app.poutput("legacy output")
            assert wait_for(lambda: any("legacy output" in row for row in terminal.screen.display))
            assert terminal.screen.margins is None

    def test_abandoning_reservation_while_suspended_restores_the_legacy_display(self, terminal_harness) -> None:
        """The reservation can stop while the display is paused for a guest. There is no UI
        loop to switch the live layout on then, but the display must still come back as the
        legacy one -- filler, native toolbar, proxy -- rather than the empty reserved layout
        with no bridge behind it."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            reserved = harness.app.reserved_toolbar
            display = harness.app._command_toolbar
            with harness.app.suspend_bottom_toolbar():
                reserved.stop()
            assert reserved.bridge is None
            assert len(display._layout.container.children) == 3
            assert display._proxy is not None
            assert all(stream.serializer is None for stream in display._streams)
            harness.app.main_session.bottom_toolbar = "RECOVERED"
            display.app.invalidate()
            assert wait_for(lambda: any(row.startswith("RECOVERED") for row in terminal.screen.display))
            harness.app.poutput("legacy output")
            assert wait_for(lambda: any("legacy output" in row for row in terminal.screen.display))
        assert terminal.screen.margins is None

    def test_abandoning_reservation_while_the_pager_is_open_keeps_the_fallback_layout(self, terminal_harness) -> None:
        """The reservation can stop while the pager is on screen. Pager exit must put back the
        display's *current* layout -- the legacy one the fallback switched to -- not the
        reserved layout it saved on entry, or the toolbar stays absent after the pager."""
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            reserved = harness.app.reserved_toolbar
            display = harness.app._command_toolbar
            seen: dict[str, bool] = {}

            def stop_mid_page() -> None:
                emitted_before = len(terminal.getvalue())
                display.app.loop.call_soon_threadsafe(reserved.stop)
                assert wait_for(lambda: reserved.bridge is None)
                # The fallback must not drop out of the pager: its screen stays up, and the
                # native toolbar is visible on its bottom row while it is open. The emulator
                # does not model the alternate screen, so the flash a renderer reset would
                # cause is checked on the wire: the sequence that quits it is never sent.
                seen["toolbar"] = wait_for(lambda: terminal.screen.display[-1].startswith("STATUS"))
                seen["pager"] = terminal.screen.display[0].startswith("row 000")
                seen["stayed_in_pager"] = "\x1b[?1049l" not in terminal.getvalue()[emitted_before:]

            assert run_pager(harness, terminal, while_open=stop_mid_page)
            assert seen == {"toolbar": True, "pager": True, "stayed_in_pager": True}
            assert reserved.bridge is None
            assert len(display.app.layout.container.children) == 3
            # The fallback deferred during paging is finished once the pager closes: legacy
            # routing is in place -- the proxy installed, the reserved serializers gone -- so
            # later command output keeps the toolbar rather than scrolling it away.
            assert display._proxy is not None
            assert all(stream.serializer is None for stream in display._streams)
            output_rendered = threading.Event()

            def after_output_render(_app) -> None:
                # Proxy output precedes its asynchronous redraw. Inspect a completed frame,
                # not the transient screen between the write and the toolbar repaint.
                rows = terminal.screen.display
                if any("after the pager" in row for row in rows) and rows[-1].startswith("STATUS"):
                    output_rendered.set()

            display.app.after_render += after_output_render
            try:
                harness.app.poutput("after the pager")
                assert output_rendered.wait(5)
            finally:
                display.app.after_render -= after_output_render
            harness.app.main_session.bottom_toolbar = "RECOVERED"
            display.app.invalidate()
            assert wait_for(lambda: terminal.screen.display[-1].startswith("RECOVERED"))
        assert terminal.screen.margins is None

    def test_the_pager_draws_its_content_over_the_reserved_toolbar(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            assert run_pager(harness, terminal), "the pager never drew its content"
            # The toolbar is suppressed again for ordinary output once the pager has closed.
            assert harness.app.reserved_toolbar.bridge._render_suppressed is True
        assert terminal.screen.margins is None

    @pytest.mark.parametrize("quit_key", [False, True])
    @pytest.mark.parametrize("failure", ["erase", "request_absolute_cursor_position"])
    def test_pager_teardown_restores_the_display_even_if_leaving_raises(
        self, terminal_harness, monkeypatch, quit_key, failure
    ) -> None:
        """If the display cannot run the pager's exit on its own loop -- here the exit's erase
        raises -- page() must still put the display back itself. Left as the pager's, the
        full-screen flag and editing mode would carry into the next main prompt."""
        harness, terminal = terminal_harness
        created: list[Any] = []
        real_pager = command_toolbar.Pager

        def make_pager(*args: Any, **kwargs: Any) -> Any:
            pager = real_pager(*args, **kwargs)
            created.append(pager)
            return pager

        monkeypatch.setattr(command_toolbar, "Pager", make_pager)
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            display = harness.app._command_toolbar
            bindings = display.app.key_bindings
            editing_mode = display.app.editing_mode

            original = getattr(display.app.renderer, failure)
            forced_close = threading.Event()

            def exit_fails() -> None:
                monkeypatch.setattr(display.app.renderer, failure, original)
                raise ValueError("exit failed")

            def drive() -> None:
                assert wait_for(lambda: terminal.screen.display[0].startswith("row 000"))
                monkeypatch.setattr(display.app.renderer, failure, exit_fails)
                if quit_key:
                    harness.pipe.send_text("q")
                    if not wait_for(created[0].closed.is_set, timeout=3):
                        forced_close.set()
                        created[0].closed.set()
                else:
                    created[0].closed.set()

            with ThreadPoolExecutor() as executor:
                future = executor.submit(drive)
                with pytest.raises(ValueError, match="exit failed"):
                    display.page(PAGER_BODY, chop=False)
                future.result(timeout=5)

            assert not forced_close.is_set(), "the quit callback failed to release page()"
            assert display.app.full_screen is False
            assert display.app.renderer.full_screen is False
            assert display.app.layout is display._layout
            assert display.app.key_bindings is display._bindings or display.app.key_bindings is bindings
            assert display.app.editing_mode is editing_mode
            assert harness.app.reserved_toolbar.bridge._render_suppressed is True
            harness.app.stdout.write("PARTIAL")
            harness.app.stdout.flush()
            display._call_in_ui(display.app._redraw)
            harness.app.stdout.write("END\n")
            harness.app.stdout.flush()
            assert any("PARTIALEND" in row for row in terminal.screen.display)

    def test_output_that_fits_is_printed_without_a_pager(self, terminal_harness) -> None:
        harness, terminal = terminal_harness
        with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
            harness.app._command_toolbar.page("one short line", chop=False)
            assert any(row.startswith("one short line") for row in terminal.screen.display)
            assert terminal.screen.display[-1].startswith("STATUS")
