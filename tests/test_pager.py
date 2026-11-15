"""Tests for the built-in pager view."""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import ANSI, fragment_list_to_text, to_formatted_text
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.input.typeahead import get_typeahead
from rich.console import Console

from cmd2 import pager as pager_module
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


def parsed_whole(text: str) -> tuple[str, list[list[tuple[str, str]]]]:
    """Return the text and styled lines prompt-toolkit makes of captured output parsed in one piece.

    This is what the pager showed when it parsed everything before showing anything.
    """
    fragments = to_formatted_text(ANSI(pager_module._OSC_RE.sub("", text).removesuffix("\n")))
    lines = [[(style, char) for style, char, *_ in line if char] for line in split_lines(fragments)]
    return fragment_list_to_text(fragments), lines


def shown_by_pager(text: str) -> tuple[str, list[list[tuple[str, str]]]]:
    """Return the text of a pager's view, and each of its lines as the view styles it."""
    view = Pager(text, chop=False).text
    get_line = view.lexer.lex_document(view.document)
    lines = [[(style, char) for style, char, *_ in get_line(number) if char] for number in range(view.document.line_count)]
    return view.text, lines


RICH = Console(force_terminal=True, color_system="truecolor", no_color=False, legacy_windows=False, width=60)


def rich_output(*renderables: object) -> str:
    with RICH.capture() as capture:
        for renderable in renderables:
            RICH.print(renderable)
    return capture.get()


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="nothing"),
        pytest.param("\n", id="one empty line"),
        pytest.param("plain\ntext\n\nwith a gap", id="plain text"),
        pytest.param("\x1b[31mred\x1b[0m plain \x1b[1;32mbold green\x1b[0m\nnext", id="styles closed on their line"),
        pytest.param("\x1b[31mred\nstill red\n\x1b[1mand bold\x1b[0m\nplain", id="a style left open across lines"),
        pytest.param("\x1b[31mred\n\x1b[39mdefault\n\x1b[4munderlined\nstill\x1b[m\nplain", id="styles ended without a reset"),
        pytest.param("\x1b[38;5;196mindexed\x1b[0m \x1b[38;2;1;2;3mtrue color\x1b[0m", id="indexed and true color"),
        pytest.param("a\x1b[5Cb\x1b[Cc", id="cursor forward becomes spaces"),
        pytest.param("a\x1b[2Kb\x1b[?25lc\x1b[Hd", id="other control sequences"),
        pytest.param("a\x1bXb\x1b\nc", id="an escape which starts no control sequence"),
        pytest.param("a\x1b[31\nb\x1b[0mc", id="a newline inside a control sequence"),
        pytest.param("a\x1b[31", id="a control sequence cut short"),
        pytest.param("a\x1b", id="an escape cut short"),
        pytest.param("\x9b31mred\x9b0m plain \x9b2Cgap", id="one-character sequence introducer"),
        pytest.param("\x1b\x1b[31mnot red", id="an escape before a control sequence"),
        pytest.param("\u754c\x1b[31m\u754c\u754c\x1b[0m e\u0301 \U0001f600", id="wide and combining characters"),
        pytest.param("line\r\nwith\tcontrols\x00", id="other control characters"),
        pytest.param(
            rich_output("[bold red]bold red[/bold red] plain [link=https://example.com]linked[/link]"), id="Rich markup"
        ),
        pytest.param(rich_output("[on blue]" + "word " * 40), id="a Rich style wrapped over several lines"),
    ],
)
def test_pager_shows_what_parsing_the_whole_text_showed(text) -> None:
    """Parsing a line when it is shown gives the text and styles that parsing everything first gave."""
    assert shown_by_pager(text) == parsed_whole(text)


def test_pager_shows_what_parsing_the_whole_text_showed_for_arbitrary_input() -> None:
    """The same, for input nobody thought of: escapes and their parts in every order."""
    pieces = ["\x1b", "[", "0", "1", "3", "9", ";", "m", "C", "?", "\x9b", "\r", "a", "\u754c", " ", "\n", "\n"]
    whole = ["\x1b[31m", "\x1b[1m", "\x1b[4;32m", "\x1b[39m", "\x1b[22m", "\x1b[0m", "\x1b[m", "\x1b[0;33m"]
    randomizer = random.Random(1743)
    for _ in range(3000):
        text = "".join(randomizer.choices(pieces + whole, k=randomizer.randrange(24)))
        assert shown_by_pager(text) == parsed_whole(text), repr(text)


def test_pager_leaves_out_zero_width_markers() -> None:
    """Readline's markers, and what is between them, are for a prompt and never shown."""
    assert shown_by_pager("a\x01\x1b[31m\x02b\nc\x01unfinished\nd") == ("ab\nc", [[("", "a"), ("", "b")], [("", "c")]])


def test_pager_parses_only_the_lines_it_is_asked_for(monkeypatch) -> None:
    """Opening a pager on a long text costs no more than opening one on a short text.

    prompt-toolkit's parser makes a fragment of every character. Parsing 100,000 lines
    before showing any took two seconds and a gigabyte.
    """
    parsed = []

    def counting(value: str) -> ANSI:
        parsed.append(value)
        return ANSI(value)

    monkeypatch.setattr(pager_module, "ANSI", counting)
    text = "\n".join(f"\x1b[32mrow {number}\x1b[0m of output" for number in range(5000))

    assert not output_fits(text, 80, 23, chop=False)
    view = Pager(text, chop=False).text
    assert parsed == []

    get_line = view.lexer.lex_document(view.document)
    assert [char for _, char, *_ in get_line(4999)] == list("row 4999 of output")
    assert get_line(4999)[0][0] == "ansigreen"
    assert get_line(4999) is get_line(4999)
    assert parsed == ["\x1b[32mrow 4999\x1b[0m of output"]


@pytest.mark.parametrize("chop", [False, True])
def test_output_fits_measures_only_text_short_enough_to_fit(monkeypatch, chop) -> None:
    """Text with more lines than rows cannot fit, however narrow, so none of it is measured."""
    monkeypatch.setattr(pager_module, "get_cwidth", mock.Mock(side_effect=AssertionError("measured")))
    monkeypatch.setattr(pager_module, "UIContent", mock.Mock(side_effect=AssertionError("measured")))

    assert not output_fits("\x1b[31mrow\x1b[0m\n" * 24, 80, 23, chop=chop)
    assert not output_fits("", 80, 0, chop=chop)


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
        # Use the size this frame was drawn at. The terminal may have been resized since,
        # and an error raised here stops the display.
        size = ui.renderer._last_size
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


@pytest.mark.parametrize("chop", [False, True])
def test_pager_half_page_scrolling(toolbar_app, chop) -> None:
    """Half-page keys move half of what the full-page keys move, and never zero rows."""
    app, pipe, _ = toolbar_app
    lines = [f"row {index:03d}" for index in range(200)]

    def script(keys) -> None:
        page_rows = max(1, keys.pager.text.window.render_info.window_height - 1)
        half_rows = max(1, int(page_rows * 0.5))
        # A half page has to be a distinct, smaller step for this test to mean
        # anything. The pager's own arithmetic is what decides the row it lands on.
        assert 0 < half_rows < page_rows
        keys.press("d", row=half_rows)
        keys.press("d", row=2 * half_rows)
        keys.press("u", row=half_rows)
        keys.press("\x04", row=2 * half_rows)  # Ctrl-D.
        keys.press("\x15", row=half_rows)  # Ctrl-U.
        # Half-page steps stay half a page next to a full one taken from the same row.
        keys.press("g", row=0)
        keys.press("\x1b[6~", row=page_rows)  # Page Down.

    drive_pager(app, pipe, "\n".join(lines), chop=chop, script=script)


@pytest.mark.parametrize("key", ["\x1b", "\x03"], ids=["escape", "ctrl-c"])
def test_pager_search_abort_keys(toolbar_app, key) -> None:
    """Escape and Ctrl-C abort a search rather than closing the pager.

    While the search field has focus the pager's own close bindings are filtered out,
    so these keys have to reach prompt-toolkit's search bindings instead. Those are
    registered explicitly so that they still work when the main prompt uses Vi mode.
    """
    app, pipe, _ = toolbar_app
    lines = [f"row {index:03d}" for index in range(100)]

    def script(keys) -> None:
        keys.press("j", row=1)
        # Typing a search previews it without moving the pager's own cursor.
        keys.press("/row 05", row=1)
        # Aborting restores the row the search started from instead of quitting.
        keys.press(key, row=1)
        # Focus is back on the pager, so ordinary navigation works again.
        keys.press("j", row=2)

    drive_pager(app, pipe, "\n".join(lines), chop=False, script=script)


@pytest.mark.parametrize("key", ["\x1b", "\x03", "q"], ids=["escape", "ctrl-c", "q"])
def test_pager_close_keys(toolbar_app, key) -> None:
    """Each close key ends the pager without leaving the keystroke for the next prompt.

    Escape is bound eagerly, and it is also the first byte of every arrow and page
    key. Closing on a bare Escape must therefore not come at the cost of the escape
    sequences that arrive with more bytes behind them.
    """
    app, pipe, _ = toolbar_app
    entered = threading.Event()
    closed = threading.Event()

    def observe(ui) -> None:
        if ui.full_screen:
            entered.set()

    def interact() -> None:
        assert entered.wait(5), "pager never opened"
        # Scroll first, so the pager is known to be reading keys before the close key.
        pipe.send_text("j")
        pipe.send_text(key)
        if not closed.wait(5):
            # Rescue the blocked main thread so this fails as an assertion, not a hang.
            pipe.send_text("q")
            raise AssertionError(f"{key!r} did not close the pager")

    app.main_session.app.after_render += observe
    with ThreadPoolExecutor() as executor:
        interaction = executor.submit(interact)
        try:
            with app._command_toolbar_context():
                app._command_toolbar.page("\n".join(f"row {index:03d}" for index in range(200)), chop=False)
        finally:
            closed.set()
        interaction.result(timeout=10)
    assert get_typeahead(pipe) == []
