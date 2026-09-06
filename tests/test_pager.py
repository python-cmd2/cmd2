"""Tests for the built-in pager view."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.typeahead import get_typeahead
from rich.console import Console

from cmd2.pager import Pager, output_fits


@pytest.mark.parametrize("chop", [False, True])
def test_pager_styles_and_wrapping(chop) -> None:
    pager = Pager("\x1b[31m" + "界" * 40 + "\x1b[0m\n", chop=chop)
    assert pager.text.text == "界" * 40
    assert pager.text.read_only
    lexer = pager.text.lexer.lex_document(pager.text.document)
    assert "ansired" in lexer(0)[0][0]


@pytest.mark.parametrize("chop", [False, True])
@pytest.mark.parametrize("terminator", ["\x1b\\", "\x07"], ids=["ST", "BEL"])
def test_pager_rich_hyperlinks(chop, terminator) -> None:
    # legacy_windows=False keeps rich from suppressing OSC 8 hyperlinks when the
    # tests run against a legacy Windows console.
    console = Console(force_terminal=True, color_system="standard", no_color=False, legacy_windows=False)
    with console.capture() as capture:
        console.print("[link=https://example.com][red]click here[/red][/link] after")
    captured = capture.get()
    assert "\x1b]8;" in captured
    captured = captured.replace("\x1b\\", terminator)

    pager = Pager(captured, chop=chop)
    assert pager.text.text == "click here after"
    lexer = pager.text.lexer.lex_document(pager.text.document)
    assert "ansired" in lexer(0)[0][0]
    assert output_fits(captured, len("click here after"), 1, chop=chop)
    assert not output_fits(captured, len("click here after") - 1, 1, chop=chop)


@pytest.mark.parametrize("chop", [False, True])
def test_output_fits_measures_styled_and_wide_text(chop) -> None:
    # Forty double-width characters occupy eighty columns, and styling them adds
    # escape sequences that must not count towards the measurement.
    text = "\x1b[31m" + "界" * 40 + "\x1b[0m\n"
    assert not output_fits(text, 20, 1, chop=chop)
    # Wrapping the line onto four rows fits; chopping keeps it one wide row that does not.
    assert output_fits(text, 20, 5, chop=chop) is (not chop)
    assert output_fits(text, 100, 1, chop=chop)


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


class PagerKeys:
    """Send keys to the built-in pager and wait for the frame that reflects them."""

    def __init__(self, app, pipe, pager) -> None:
        self.pipe = pipe
        self.pager = pager
        self.presses = 0
        self.states = []
        self.updated = threading.Condition()
        ui = app.main_session.app
        ui.key_processor.after_key_press += self._count
        ui.after_render += self._record

    def _count(self, _) -> None:
        with self.updated:
            self.presses += 1

    def _record(self, _) -> None:
        # Read the pager's own buffer, not the focused one, which is the search field
        # while a search is being typed. Read it after rendering, because
        # prompt-toolkit settles the window's scroll offsets while it draws.
        with self.updated:
            self.states.append(
                (
                    self.presses,
                    self.pager.text.buffer.document.cursor_position_row,
                    self.pager.text.window.horizontal_scroll,
                )
            )
            self.updated.notify_all()

    def press(self, keys, row, column=0) -> None:
        """Send keys and wait for a drawn frame that shows the expected position."""
        with self.updated:
            handled = self.presses
        self.pipe.send_text(keys)
        deadline = time.monotonic() + 5
        index = 0
        with self.updated:
            while True:
                while index < len(self.states):
                    presses, *position = self.states[index]
                    index += 1
                    if presses > handled and position == [row, column]:
                        return
                remaining = deadline - time.monotonic()
                notified = remaining > 0 and self.updated.wait(remaining)
                assert notified, f"pager ignored {keys!r}: wanted {(row, column)}, saw {self.states[-3:]}"


def drive_pager(app, pipe, text, *, chop, script) -> None:
    """Page text and run script against its keys while the pager is displayed."""
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
            script(PagerKeys(app, pipe, created[0]))
        finally:
            pipe.send_text("q")

    app.main_session.app.after_render += observe
    with mock.patch("cmd2.command_toolbar.Pager", side_effect=make_pager), ThreadPoolExecutor() as executor:
        interaction = executor.submit(interact)
        with app._command_toolbar_context():
            app._command_toolbar.page(text, chop=chop)
        interaction.result(timeout=10)
    assert get_typeahead(pipe) == []


def test_pager_vertical_scrolling_keeps_horizontal_position(toolbar_app) -> None:
    app, pipe, _ = toolbar_app
    # Wide rows are what chopped output is for. Scrolling right to read a column and
    # then moving down a row must not throw that column away.
    text = "\n".join(f"row {index:03d} " + "col " * 40 for index in range(100))

    def script(keys) -> None:
        keys.press("\x1b[C", row=0, column=40)
        keys.press("j", row=1, column=40)
        keys.press("k", row=0, column=40)

    drive_pager(app, pipe, text, chop=True, script=script)


@pytest.mark.parametrize("chop", [False, True])
def test_pager_navigation_keys(toolbar_app, chop) -> None:
    app, pipe, _ = toolbar_app
    lines = [f"row {index:03d}" for index in range(100)]
    lines[3] = ""  # A line with no columns for a scroll target to be clamped against.

    def script(keys) -> None:
        keys.press("\x1b[B", row=1)  # Down arrow.
        keys.press("\x1b[A", row=0)  # Up arrow.
        page_rows = keys.pager.text.window.render_info.window_height - 1
        keys.press("\x1b[6~", row=page_rows)  # Page Down.
        keys.press("\x1b[5~", row=0)  # Page Up.
        keys.press("\r", row=1)
        keys.press("\x1b[A", row=0)
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

    drive_pager(app, pipe, "\n".join(lines), chop=chop, script=script)


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
