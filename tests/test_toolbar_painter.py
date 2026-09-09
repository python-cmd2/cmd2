"""Tests for laying toolbar content out as display cells.

Cells, not string length: a frame is a grid of what the terminal will show, so that comparing
two frames answers "will the user see a difference" rather than "did the Python string
change". Wide characters occupy two cells, combining characters occupy none of their own, and
a wide character is never split across the right edge.
"""

import pytest

from cmd2.toolbar_painter import Cell, ToolbarFrame, measure_toolbar_height


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
