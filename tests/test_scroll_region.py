"""Tests for the reserved-bottom-row scroll region and its margin-bounded erase."""

import io

import pytest
from prompt_toolkit.output.vt100 import Vt100_Output

from cmd2 import scroll_region as sr


def make_output(rows: int = 24, cols: int = 80) -> tuple[Vt100_Output, io.StringIO]:
    stream = io.StringIO()
    return Vt100_Output(
        stream, lambda: __import__("prompt_toolkit.data_structures", fromlist=["Size"]).Size(rows, cols)
    ), stream


class TestSequences:
    def test_scroll_region_is_anchored_at_row_one(self) -> None:
        """Anchoring at row 1 is required or lines scrolled out never reach scrollback."""
        assert sr.scroll_region_sequence(24, 1) == "\x1b[1;23r"

    def test_scroll_region_honors_multiple_reserved_rows(self) -> None:
        assert sr.scroll_region_sequence(24, 3) == "\x1b[1;21r"

    def test_reset_sequence_restores_full_screen_margins(self) -> None:
        assert sr.reset_scroll_region_sequence() == "\x1b[r"

    def test_bounded_erase_uses_delete_line_not_erase_display(self) -> None:
        """ED ignores the margins; DL is bounded by them, so the pinned row survives."""
        seq = sr.bounded_erase_down_sequence()
        assert seq.endswith("M"), f"expected a DL sequence, got {seq!r}"
        assert "J" not in seq, "must not use ED, which ignores the scroll margins"

    @pytest.mark.parametrize(("total", "reserved"), [(24, 0), (24, 24), (24, 25), (1, 1), (24, -1)])
    def test_rejects_regions_that_would_leave_no_usable_rows(self, total: int, reserved: int) -> None:
        with pytest.raises(ValueError, match=r"reserved_rows must be at least 1|leaves no usable rows"):
            sr.scroll_region_sequence(total, reserved)


class TestReservedBottomRows:
    def test_sets_the_region_on_enter_and_resets_it_on_exit(self) -> None:
        output, stream = make_output(rows=24)
        with sr.ReservedBottomRows(output, reserved_rows=1):
            output.flush()
            assert "\x1b[1;23r" in stream.getvalue()
        output.flush()
        assert stream.getvalue().endswith("\x1b[r")

    def test_erase_down_is_bounded_while_reserved(self) -> None:
        output, stream = make_output(rows=24)
        with sr.ReservedBottomRows(output, reserved_rows=1):
            output.flush()
            stream.truncate(0), stream.seek(0)
            output.erase_down()
            output.flush()
            written = stream.getvalue()
        assert "\x1b[J" not in written, "unbounded ED would destroy the reserved row"
        assert written.endswith("M")

    def test_bounded_erase_clears_the_whole_usable_region(self) -> None:
        """A DL count of 1 (or 0, which terminals read as 1) would clear one row, not the region."""
        output, stream = make_output(rows=24)
        with sr.ReservedBottomRows(output, reserved_rows=2) as region:
            output.flush()  # drain the region sequence out of prompt_toolkit's buffer first
            stream.truncate(0), stream.seek(0)
            output.erase_down()
            output.flush()
        assert stream.getvalue() == f"\x1b[{region.usable_rows}M"

    def test_original_erase_down_is_restored_on_exit(self) -> None:
        output, stream = make_output(rows=24)
        original = output.erase_down
        with sr.ReservedBottomRows(output, reserved_rows=1):
            assert output.erase_down != original
        assert output.erase_down == original
        stream.truncate(0), stream.seek(0)
        output.erase_down()
        output.flush()
        assert "\x1b[J" in stream.getvalue()

    def test_region_is_reset_even_if_the_body_raises(self) -> None:
        output, stream = make_output(rows=24)
        with pytest.raises(RuntimeError), sr.ReservedBottomRows(output, reserved_rows=1):
            raise RuntimeError("boom")
        output.flush()
        assert stream.getvalue().endswith("\x1b[r")

    def test_usable_rows_excludes_the_reserved_rows(self) -> None:
        output, _ = make_output(rows=24)
        region = sr.ReservedBottomRows(output, reserved_rows=2)
        assert region.usable_rows == 22
