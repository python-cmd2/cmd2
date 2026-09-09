"""Tests for the pure sequence builders behind the reserved bottom row.

Installing these sequences, and deciding when it is legal to, belongs to
``tests/test_terminal_display.py`` and ``tests/test_reserved_output.py``.
"""

import pytest

from cmd2 import scroll_region as sr


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

    def test_bounded_erase_screen_clears_the_region_and_homes_within_it(self) -> None:
        """ED2 erases the whole display; the bounded form must stop at the margin."""
        seq = sr.bounded_erase_screen_sequence(23)
        assert seq == "\x1b[1;1H\x1b[23M"
        assert "\x1b[2J" not in seq, "ED2 would erase the reserved rows"

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
