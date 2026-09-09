"""Tests for laying toolbar content out as display cells.

Cells, not string length: a frame is a grid of what the terminal will show, so that comparing
two frames answers "will the user see a difference" rather than "did the Python string
change". Wide characters occupy two cells, combining characters occupy none of their own, and
a wide character is never split across the right edge.
"""

import io
import re
import threading

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.styles import BaseStyle, DummyStyle

from cmd2.terminal_display import Geometry
from cmd2.terminal_transaction import TerminalLock, current_transaction, held_higher_level_locks
from cmd2.toolbar_painter import Cell, ToolbarFrame, ToolbarPainter, measure_toolbar_height


def text_of(frame: ToolbarFrame, row: int = 0) -> str:
    """Join one row's cells into the text a terminal would show."""
    return "".join(cell.char for cell in frame.rows[row])


def styles_of(frame: ToolbarFrame, row: int = 0) -> list[str]:
    """List one row's per-cell styles."""
    return [cell.style for cell in frame.rows[row]]


class TestShape:
    def test_a_frame_is_always_exactly_its_declared_size(self) -> None:
        frame = ToolbarFrame.build("hi", width=10, height=2)
        assert len(frame.rows) == 2
        assert all(len(row) == 10 for row in frame.rows)

    def test_short_content_is_padded_with_default_style_spaces(self) -> None:
        """The pad is what overwrites a longer previous frame; it is part of the content."""
        frame = ToolbarFrame.build([("class:toolbar", "hi")], width=5, height=1, default_style="class:toolbar")
        assert text_of(frame) == "hi   "
        assert styles_of(frame) == ["class:toolbar"] * 5

    def test_content_wider_than_the_terminal_wraps(self) -> None:
        frame = ToolbarFrame.build("abcdef", width=3, height=2)
        assert text_of(frame, 0) == "abc"
        assert text_of(frame, 1) == "def"

    def test_content_taller_than_the_band_is_truncated(self) -> None:
        """Growing past the band is a geometry transition, never a write outside it."""
        frame = ToolbarFrame.build("one\ntwo\nthree", width=10, height=2)
        assert text_of(frame, 0) == "one       "
        assert text_of(frame, 1) == "two       "

    def test_an_explicit_newline_starts_a_row(self) -> None:
        frame = ToolbarFrame.build("a\nb", width=3, height=2)
        assert text_of(frame, 0) == "a  "
        assert text_of(frame, 1) == "b  "

    def test_empty_content_is_a_blank_frame(self) -> None:
        frame = ToolbarFrame.build("", width=4, height=1)
        assert text_of(frame) == "    "

    def test_frames_with_the_same_cells_are_equal(self) -> None:
        assert ToolbarFrame.build("hi", width=4, height=1) == ToolbarFrame.build("hi", width=4, height=1)

    def test_a_style_only_change_is_not_equal(self) -> None:
        """Same text, different attributes, is a visible change and must not compare equal."""
        plain = ToolbarFrame.build([("", "hi")], width=4, height=1)
        bold = ToolbarFrame.build([("bold", "hi")], width=4, height=1)
        assert plain != bold


class TestStyles:
    def test_each_fragment_styles_its_own_cells(self) -> None:
        frame = ToolbarFrame.build([("bold", "ab"), ("italic", "c")], width=4, height=1, default_style="base")
        assert styles_of(frame) == ["bold", "bold", "italic", "base"]

    def test_a_zero_width_escape_fragment_is_dropped(self) -> None:
        """Passing arbitrary cursor control through the painter would move the real cursor."""
        content = [("", "a"), ("[ZeroWidthEscape]", "\x1b[6n"), ("", "b")]
        frame = ToolbarFrame.build(content, width=4, height=1)
        assert text_of(frame) == "ab  "

    def test_a_mouse_handler_fragment_keeps_its_text_and_style(self) -> None:
        """Handlers are not supported in the band; the visible part still renders."""
        content = [("bold", "click", lambda event: None)]
        frame = ToolbarFrame.build(content, width=6, height=1)
        assert text_of(frame) == "click "
        assert styles_of(frame)[0] == "bold"


class TestCellWidths:
    def test_a_wide_character_occupies_two_cells(self) -> None:
        frame = ToolbarFrame.build("广", width=4, height=1)
        assert frame.rows[0][0].char == "广"
        assert frame.rows[0][1].char == ""
        assert frame.rows[0][1].is_continuation is True
        assert text_of(frame) == "广  "

    def test_a_wide_character_is_never_split_at_the_right_edge(self) -> None:
        """Half a wide character at the edge is what wraps a row into the one below it."""
        frame = ToolbarFrame.build("a广", width=2, height=2)
        assert text_of(frame, 0) == "a "
        assert frame.rows[1][0].char == "广"

    def test_the_pad_before_a_wrapped_wide_character_uses_the_default_style(self) -> None:
        frame = ToolbarFrame.build([("bold", "a广")], width=2, height=2, default_style="base")
        assert styles_of(frame, 0) == ["bold", "base"]

    def test_a_combining_character_joins_the_cell_before_it(self) -> None:
        frame = ToolbarFrame.build("e\u0301x", width=4, height=1)
        assert frame.rows[0][0].char == "e\u0301"
        assert frame.rows[0][1].char == "x"

    def test_a_leading_combining_character_gets_its_own_cell(self) -> None:
        """There is nothing to combine with; dropping it would silently lose content."""
        frame = ToolbarFrame.build("\u0301a", width=4, height=1)
        assert frame.rows[0][0].char == "\u0301"
        assert frame.rows[0][1].char == "a"

    def test_a_tab_advances_to_the_next_tab_stop(self) -> None:
        frame = ToolbarFrame.build("a\tb", width=12, height=1)
        assert text_of(frame) == "a       b   "

    def test_a_carriage_return_does_not_reach_the_terminal(self) -> None:
        """A stray CR would move the cursor within the band rather than print."""
        frame = ToolbarFrame.build("a\rb", width=4, height=1)
        assert text_of(frame) == "ab  "


class TestMeasurement:
    def test_a_short_toolbar_is_one_row(self) -> None:
        assert measure_toolbar_height("hi", width=10) == 1

    def test_wrapping_is_counted(self) -> None:
        assert measure_toolbar_height("abcdef", width=3) == 2

    def test_newlines_are_counted(self) -> None:
        assert measure_toolbar_height("a\nb\nc", width=10) == 3

    def test_empty_content_still_measures_one_row(self) -> None:
        """An empty toolbar is an intentional visibility change, not a zero-row reservation."""
        assert measure_toolbar_height("", width=10) == 1

    def test_measurement_matches_the_frame_it_would_build(self) -> None:
        content = [("bold", "wide 广 content that wraps around")]
        height = measure_toolbar_height(content, width=12)
        frame = ToolbarFrame.build(content, width=12, height=height)
        # Nothing was truncated: the last row is where the content ended.
        assert measure_toolbar_height(content, width=12) == len(frame.rows)
        assert text_of(frame, height - 1).strip() != ""


class TestValidation:
    def test_a_frame_needs_a_positive_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            ToolbarFrame.build("hi", width=0, height=1)

    def test_a_frame_needs_a_positive_height(self) -> None:
        with pytest.raises(ValueError, match="height"):
            ToolbarFrame.build("hi", width=4, height=0)

    def test_a_cell_reports_its_display_width(self) -> None:
        assert Cell("a", "").width == 1
        assert Cell("广", "").width == 2
        assert Cell("", "", is_continuation=True).width == 0

    def test_measuring_needs_a_positive_width(self) -> None:
        with pytest.raises(ValueError, match="width"):
            measure_toolbar_height("hi", width=0)

    def test_a_frame_reports_its_own_size(self) -> None:
        frame = ToolbarFrame.build("hi", width=6, height=2)
        assert (frame.height, frame.width) == (2, 6)

    def test_an_empty_frame_reports_zero_width(self) -> None:
        assert ToolbarFrame(rows=()).width == 0

    def test_a_tab_wraps_when_it_reaches_the_edge(self) -> None:
        """The expansion is cells, so it wraps like any other run of them."""
        frame = ToolbarFrame.build("a\tb", width=4, height=3)
        assert text_of(frame, 0) == "a   "
        assert text_of(frame, 1) == "    "
        assert text_of(frame, 2) == "b   "


class Recorder(Vt100_Output):
    """A backend that records what it was asked to do, and when."""

    def __init__(self, stream: io.StringIO) -> None:
        super().__init__(stream, lambda: Size(rows=24, columns=80))
        self.flushes = 0
        self.transaction_during_write: list[object] = []

    def write_raw(self, data: str) -> None:
        self.transaction_during_write.append(current_transaction())
        super().write_raw(data)

    def flush(self) -> None:
        self.flushes += 1
        super().flush()


def make_painter(style: BaseStyle | None = None) -> tuple[ToolbarPainter, Recorder, io.StringIO]:
    """Build a painter over a recording backend."""
    stream = io.StringIO()
    output = Recorder(stream)
    painter = ToolbarPainter(
        output=output,
        lock=TerminalLock(),
        style=style or DummyStyle(),
        color_depth=ColorDepth.DEPTH_8_BIT,
    )
    return painter, output, stream


def geometry(rows: int = 24, columns: int = 5, reserved: int = 1) -> Geometry:
    """Build a geometry snapshot for the band."""
    return Geometry(generation=1, physical_rows=rows, columns=columns, reserved_rows=reserved)


def visible(stream: io.StringIO) -> str:
    """Strip SGR sequences, leaving cursor motion and text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", stream.getvalue())


def paint(painter: ToolbarPainter, content: AnyFormattedText, geo: Geometry) -> bool:
    """Prepare and paint content in one step, as a refresh would."""
    prepared = painter.prepare(lambda: content, width=geo.columns, height=geo.reserved_rows)
    assert prepared is not None
    return painter.paint(prepared, geo)


class TestPainting:
    def test_the_first_paint_writes_the_whole_band_at_its_physical_row(self) -> None:
        painter, _output, stream = make_painter()
        assert paint(painter, "hi", geometry()) is True
        assert "\x1b[24;1H" in visible(stream)
        assert "hi   " in visible(stream)

    def test_a_multirow_band_writes_each_row_at_its_own_physical_row(self) -> None:
        painter, _output, stream = make_painter()
        paint(painter, "ab\ncd", geometry(rows=24, columns=2, reserved=2))
        written = visible(stream)
        assert "\x1b[23;1Hab" in written
        assert "\x1b[24;1Hcd" in written

    def test_an_unchanged_frame_emits_nothing(self) -> None:
        """Same cells and attributes: the toolbar produces no output at all."""
        painter, _output, _stream = make_painter()
        paint(painter, "hi", geometry())
        _painter, output, stream = painter, _output, _stream
        before = stream.getvalue()
        flushes = output.flushes
        assert paint(painter, "hi", geometry()) is False
        assert stream.getvalue() == before
        assert output.flushes == flushes

    def test_only_the_changed_run_is_rewritten(self) -> None:
        painter, _output, stream = make_painter()
        paint(painter, "abcd", geometry(columns=5))
        stream.truncate(0)
        stream.seek(0)
        paint(painter, "abXd", geometry(columns=5))
        written = visible(stream)
        assert "\x1b[24;3HX" in written
        assert "abX" not in written

    def test_nothing_is_cleared_before_painting(self) -> None:
        """An erase before the write is exactly the flicker this design exists to remove."""
        painter, _output, stream = make_painter()
        paint(painter, "abcd", geometry())
        paint(painter, "z", geometry())
        written = stream.getvalue()
        for erase in ("\x1b[K", "\x1b[0K", "\x1b[2K", "\x1b[J", "\x1b[M"):
            assert erase not in written

    def test_a_shorter_frame_pads_its_tail_rather_than_erasing_it(self) -> None:
        painter, _output, stream = make_painter()
        paint(painter, "abcd", geometry(columns=5))
        stream.truncate(0)
        stream.seek(0)
        paint(painter, "z", geometry(columns=5))
        written = visible(stream)
        # The final column was already blank in the previous frame, so it is not rewritten:
        # the run stops where the difference does.
        assert "\x1b[24;1Hz   " in written

    def test_a_style_only_change_repaints_those_cells(self) -> None:
        painter, _output, stream = make_painter()
        paint(painter, [("", "hi")], geometry())
        stream.truncate(0)
        stream.seek(0)
        assert paint(painter, [("bold", "hi")], geometry()) is True
        assert "hi" in visible(stream)

    def test_a_wide_character_is_replaced_as_a_whole(self) -> None:
        """Both of its cells change together, so a run never begins on the right half."""
        painter, _output, stream = make_painter()
        paint(painter, "a广b", geometry(columns=5))
        stream.truncate(0)
        stream.seek(0)
        paint(painter, "aXYb", geometry(columns=5))
        assert "\x1b[24;2HXY" in visible(stream)

    def test_the_cursor_is_saved_and_restored_around_the_paint(self) -> None:
        painter, _output, stream = make_painter()
        paint(painter, "hi", geometry())
        written = stream.getvalue()
        assert written.startswith("\x1b7")
        assert written.endswith("\x1b8")

    def test_autowrap_is_disabled_during_the_paint_and_restored(self) -> None:
        """Writing the last column with autowrap on would push the band into another row."""
        painter, _output, stream = make_painter()
        paint(painter, "hi", geometry())
        written = stream.getvalue()
        assert written.index("\x1b[?7l") < written.index("\x1b[24;1H")
        assert written.index("\x1b[?7h") > written.index("\x1b[24;1H")

    def test_the_paint_is_flushed(self) -> None:
        painter, output, _stream = make_painter()
        paint(painter, "hi", geometry())
        assert output.flushes >= 1

    def test_every_write_happens_inside_a_terminal_transaction(self) -> None:
        painter, output, _stream = make_painter()
        paint(painter, "hi", geometry())
        assert output.transaction_during_write
        assert all(state is not None for state in output.transaction_during_write)

    def test_invalidating_forces_a_full_repaint(self) -> None:
        """After recovery the terminal's contents are unknown, so the diff baseline is gone."""
        painter, _output, stream = make_painter()
        paint(painter, "hi", geometry())
        painter.invalidate()
        stream.truncate(0)
        stream.seek(0)
        assert paint(painter, "hi", geometry()) is True
        assert "\x1b[24;1Hhi   " in visible(stream)

    def test_a_geometry_change_forces_a_full_repaint(self) -> None:
        """The band moved; cells matching the old frame are not on the screen any more."""
        painter, _output, stream = make_painter()
        paint(painter, "hi", geometry(rows=24))
        stream.truncate(0)
        stream.seek(0)
        assert paint(painter, "hi", geometry(rows=12)) is True
        assert "\x1b[12;1Hhi   " in visible(stream)


class TestContentEvaluation:
    def test_the_callback_runs_outside_the_terminal_transaction(self) -> None:
        """Named rule 13.2: a content callback must never run while the terminal is held."""
        painter, _output, _stream = make_painter()
        seen: list[object] = []
        painter.prepare(lambda: seen.append(current_transaction()) or "hi", width=5, height=1)
        assert seen == [None]

    def test_the_callback_runs_once_per_requested_refresh(self) -> None:
        painter, _output, _stream = make_painter()
        calls = 0

        def content() -> str:
            nonlocal calls
            calls += 1
            return "hi"

        painter.prepare(content, width=5, height=1)
        assert calls == 1

    def test_a_failing_callback_keeps_the_last_good_frame(self) -> None:
        painter, _output, stream = make_painter()
        paint(painter, "good", geometry())
        good = painter.last_frame

        def boom() -> str:
            raise RuntimeError("callback failed")

        assert painter.prepare(boom, width=5, height=1) is None
        assert painter.last_frame == good
        assert "good" in visible(stream)

    def test_a_failing_callback_is_not_called_again(self) -> None:
        """Repeated failing updates would report the same error on every refresh."""
        painter, _output, _stream = make_painter()
        calls = 0

        def boom() -> str:
            nonlocal calls
            calls += 1
            raise RuntimeError("callback failed")

        painter.prepare(boom, width=5, height=1)
        painter.prepare(boom, width=5, height=1)
        assert calls == 1

    def test_the_error_is_reported_once(self) -> None:
        painter, _output, _stream = make_painter()

        def boom() -> str:
            raise RuntimeError("callback failed")

        painter.prepare(boom, width=5, height=1)
        first = painter.take_pending_error()
        assert isinstance(first, RuntimeError)
        assert painter.take_pending_error() is None

    def test_taking_the_error_lets_content_be_evaluated_again(self) -> None:
        """Reporting is what re-arms it: the user has been told, so a retry is not a loop."""
        painter, _output, _stream = make_painter()
        failures = [True]

        def content() -> str:
            if failures[0]:
                raise RuntimeError("callback failed")
            return "recovered"

        painter.prepare(content, width=5, height=1)
        painter.take_pending_error()
        failures[0] = False
        prepared = painter.prepare(content, width=12, height=1)
        assert prepared is not None
        assert "recovered" in "".join(cell.char for cell in prepared.frame.rows[0])

    def test_empty_content_is_painted_rather_than_skipped(self) -> None:
        """An empty toolbar is an intentional visibility change and must reach the band."""
        painter, _output, stream = make_painter()
        paint(painter, "hi", geometry())
        stream.truncate(0)
        stream.seek(0)
        assert paint(painter, "", geometry()) is True
        # Only the two cells that held text are rewritten; the rest of the band was already
        # blank. Blanking by writing spaces is a paint, not an erase.
        assert "\x1b[24;1H  " in visible(stream)


class TestPaintValidation:
    def test_a_frame_that_does_not_fit_the_band_is_refused(self) -> None:
        """A resize between preparing and painting must not write outside the reservation."""
        painter, _output, _stream = make_painter()
        prepared = painter.prepare(lambda: "hi", width=5, height=1)
        assert prepared is not None
        with pytest.raises(ValueError, match="does not fit"):
            painter.paint(prepared, geometry(columns=9))

    def test_replacing_one_wide_character_with_another_repaints_both_cells(self) -> None:
        """The two halves compare equal, so the run has to be extended over the second one."""
        painter, _output, stream = make_painter()
        paint(painter, "a广b", geometry(columns=5))
        stream.truncate(0)
        stream.seek(0)
        assert paint(painter, "a国b", geometry(columns=5)) is True
        assert "\x1b[24;2H国" in visible(stream)


class BlockingStream(io.StringIO):
    """A stream whose first write blocks until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.blocked = threading.Event()
        self.entered = threading.Event()
        self.locks_held_while_blocked: tuple[str, ...] | None = None

    def write(self, text: str) -> int:
        if not self.entered.is_set():
            self.entered.set()
            self.locks_held_while_blocked = held_higher_level_locks()
            self.blocked.wait(timeout=5)
        return super().write(text)


class TestBackpressure:
    def test_paint_preserves_transaction_order_with_blocked_sink(self) -> None:
        """Named test 13.2: a blocked writer holds the terminal, and nothing slips past it."""
        stream = BlockingStream()
        output = Vt100_Output(stream, lambda: Size(rows=24, columns=5))
        lock = TerminalLock()
        painter = ToolbarPainter(
            output=output,
            lock=lock,
            style=DummyStyle(),
            color_depth=ColorDepth.DEPTH_8_BIT,
        )
        order: list[str] = []

        def command_output() -> None:
            with lock.transaction("managed write"):
                order.append("write start")
                output.write("output from a command\n")
                output.flush()
                order.append("write end")

        ready = threading.Event()

        def toolbar_paint() -> None:
            prepared = painter.prepare(lambda: "hi", width=5, height=1)
            assert prepared is not None
            ready.set()
            painter.paint(prepared, geometry())
            order.append("paint end")

        writer = threading.Thread(target=command_output)
        writer.start()
        assert stream.entered.wait(timeout=5)

        painter_thread = threading.Thread(target=toolbar_paint)
        painter_thread.start()
        assert ready.wait(timeout=5)
        # The painter has its frame and is asking for the terminal, but the blocked writer
        # holds it, so not one byte of the band can have reached the stream.
        assert "\x1b7" not in stream.getvalue()

        stream.blocked.set()
        writer.join(timeout=5)
        painter_thread.join(timeout=5)

        assert order == ["write start", "write end", "paint end"]
        written = stream.getvalue()
        assert written.index("output from a command") < written.index("\x1b7")
        # The writer blocked inside leaf I/O, holding no higher-level lock -- which is what
        # keeps the rest of cmd2 able to make progress while the terminal is backed up.
        assert stream.locks_held_while_blocked == ()
