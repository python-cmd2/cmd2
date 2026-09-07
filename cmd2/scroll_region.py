"""Reserve the bottom rows of the terminal from scrolling, with a margin-bounded erase.

A DECSTBM scroll region keeps ordinary output from scrolling through the bottom rows, so a
bottom toolbar painted there is never consumed by the scroll. On its own that is not enough:
``ED`` (``ESC [ J``), which prompt_toolkit's renderer uses to erase, ignores the scroll
margins and erases to the bottom of the display regardless. ``DL`` (``ESC [ M``) *is* bounded
by the margins, and deleting every line from the cursor to the bottom margin leaves the same
all-blank result, so it is a drop-in replacement that respects the reserved rows.

``DL`` needs no knowledge of the cursor's row, which matters because ``Output`` does not track
one. When no scroll region is set the margins cover the whole screen and the replacement
behaves exactly like ``ED``, so it is safe to leave installed.

The region must be anchored at row 1. A region starting lower orphans the rows above it: they
never scroll and so never reach the terminal's scrollback.
"""

from types import TracebackType
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.output import Output

#: Upper bound on the lines one ``DL`` may delete. Terminals clamp the count to the scroll
#: region, so any value at least as large as the tallest plausible terminal clears to the
#: bottom margin exactly.
_MAX_ROWS = 9999


def scroll_region_sequence(total_rows: int, reserved_rows: int) -> str:
    """Build the DECSTBM sequence reserving ``reserved_rows`` rows at the bottom.

    :param total_rows: height of the terminal in rows
    :param reserved_rows: number of bottom rows to keep out of the scroll region
    :return: the escape sequence setting the scroll region
    :raises ValueError: if the reservation would leave no usable rows
    """
    if reserved_rows < 1:
        raise ValueError(f"reserved_rows must be at least 1, got {reserved_rows}")
    usable = total_rows - reserved_rows
    if usable < 1:
        raise ValueError(f"reserving {reserved_rows} of {total_rows} rows leaves no usable rows")
    return f"\x1b[1;{usable}r"


def reset_scroll_region_sequence() -> str:
    """Build the sequence restoring full-screen scroll margins.

    :return: the escape sequence resetting the scroll region
    """
    return "\x1b[r"


def bounded_erase_down_sequence(rows: int = _MAX_ROWS) -> str:
    """Build a margin-bounded replacement for ``ED``.

    :param rows: maximum number of lines to delete; terminals clamp this to the scroll region
    :return: the escape sequence clearing from the cursor to the bottom margin
    """
    return f"\x1b[{rows}M"


class ReservedBottomRows:
    """Context manager reserving bottom rows and bounding the renderer's erase.

    On entry it sets the scroll region and replaces the output's ``erase_down`` with a
    margin-bounded equivalent; on exit it restores both, even if the body raises.
    """

    def __init__(self, output: "Output", reserved_rows: int = 1) -> None:
        """Initialize the region.

        :param output: the prompt_toolkit output to reserve rows on
        :param reserved_rows: number of bottom rows to keep out of the scroll region
        """
        self._output = output
        self._reserved_rows = reserved_rows
        self._total_rows = output.get_size().rows
        # Validate eagerly so a bad reservation fails at construction, not on entry.
        self._region_sequence = scroll_region_sequence(self._total_rows, reserved_rows)
        self._had_own_erase_down = False

    @property
    def usable_rows(self) -> int:
        """Number of rows available to the application, excluding the reserved rows."""
        return self._total_rows - self._reserved_rows

    def _bounded_erase_down(self) -> None:
        """Erase from the cursor to the bottom margin, leaving the reserved rows intact."""
        self._output.write_raw(bounded_erase_down_sequence(self.usable_rows))

    def __enter__(self) -> Self:
        """Set the scroll region and install the bounded erase."""
        self._output.write_raw(self._region_sequence)
        # Shadow the bound method with an instance attribute. setattr keeps this legible to
        # type checkers, which otherwise reject assigning over a method.
        self._had_own_erase_down = "erase_down" in vars(self._output)
        setattr(self._output, "erase_down", self._bounded_erase_down)  # noqa: B010
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore the original erase and full-screen scroll margins."""
        if not self._had_own_erase_down:
            delattr(self._output, "erase_down")
        self._output.write_raw(reset_scroll_region_sequence())
