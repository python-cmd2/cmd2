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

    def test_accepts_the_two_usable_row_floor(self) -> None:
        """Two usable rows is the smallest region terminals actually honour."""
        assert sr.scroll_region_sequence(3, 1) == "\x1b[1;2r"

    def test_reset_sequence_restores_full_screen_margins(self) -> None:
        assert sr.reset_scroll_region_sequence() == "\x1b[r"

    def test_bounded_erase_uses_delete_line_not_erase_display(self) -> None:
        """ED ignores the margins; DL is bounded by them, so the pinned row survives."""
        seq = sr.bounded_erase_down_sequence()
        assert seq.endswith("M"), f"expected a DL sequence, got {seq!r}"
        assert "J" not in seq, "must not use ED, which ignores the scroll margins"

    @pytest.mark.parametrize(
        ("total", "reserved"),
        [(24, 0), (24, 24), (24, 25), (1, 1), (24, -1), (24, 23), (2, 1), (3, 2)],
    )
    def test_rejects_regions_that_would_leave_too_few_usable_rows(self, total: int, reserved: int) -> None:
        with pytest.raises(ValueError, match=r"reserved_rows must be at least 1|needs at least"):
            sr.scroll_region_sequence(total, reserved)


class TestReservedBottomRows:
    def test_sets_the_region_on_enter_and_resets_it_on_exit(self) -> None:
        output, stream = make_output(rows=24)
        with sr.ReservedBottomRows(output, reserved_rows=1):
            assert "\x1b[1;23r" in stream.getvalue()
        assert stream.getvalue().endswith("\x1b[r")

    def test_the_region_reaches_the_terminal_on_entry(self) -> None:
        """Callers may rely on the reservation being in force once __enter__ returns."""
        output, stream = make_output(rows=24)
        with sr.ReservedBottomRows(output, reserved_rows=1):
            # No flush of our own: prompt_toolkit buffers write_raw, so an unflushed
            # region sequence would leave the reservation merely promised.
            assert "\x1b[1;23r" in stream.getvalue()
            assert not output._buffer

    def test_the_reset_reaches_the_terminal_without_a_further_flush(self) -> None:
        """A body that exits without another renderer operation must still be restored."""
        output, stream = make_output(rows=24)
        with sr.ReservedBottomRows(output, reserved_rows=1):
            output.flush()
        assert stream.getvalue().endswith("\x1b[r"), "margins were left restricted"
        assert not output._buffer, "the reset is still sitting in prompt_toolkit's buffer"

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
            stream.truncate(0), stream.seek(0)
            output.erase_down()
            output.flush()
            # Assert inside the region: on exit the reset is written and flushed too.
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

    def test_restores_a_pre_existing_instance_level_erase_down(self) -> None:
        """A caller's own override must survive the reservation, not be replaced by ours."""
        output, _stream = make_output(rows=24)
        calls: list[str] = []

        def caller_override() -> None:
            calls.append("caller")

        output.erase_down = caller_override  # type: ignore[method-assign]

        with sr.ReservedBottomRows(output, reserved_rows=1):
            pass

        assert output.erase_down is caller_override
        output.erase_down()
        assert calls == ["caller"], "the caller's override must be the one that runs"

    def test_region_is_reset_even_if_the_body_raises(self) -> None:
        output, stream = make_output(rows=24)
        with pytest.raises(RuntimeError), sr.ReservedBottomRows(output, reserved_rows=1):
            raise RuntimeError("boom")
        assert stream.getvalue().endswith("\x1b[r")
        assert not output._buffer

    def test_usable_rows_excludes_the_reserved_rows(self) -> None:
        output, _ = make_output(rows=24)
        region = sr.ReservedBottomRows(output, reserved_rows=2)
        assert region.usable_rows == 22
