"""Reserve the bottom rows of the terminal from scrolling, with a margin-bounded erase.

A DECSTBM scroll region keeps ordinary output from scrolling through the bottom rows, so a
bottom toolbar painted there is never consumed by the scroll. On its own that is not enough:
``ED`` (``ESC [ J``), which prompt_toolkit's renderer uses to erase, ignores the scroll
margins and erases to the bottom of the display regardless. ``DL`` (``ESC [ M``) *is* bounded
by the margins, so deleting every line from the cursor to the bottom margin clears the usable
area while leaving the reserved rows intact.

**The substitution is only valid from column zero.** ``ED`` preserves the part of the cursor's
line before the cursor; ``DL`` deletes the whole line. Measured on tmux 3.7c, running ``DL``
from a nonzero column destroyed committed text to the left of the cursor. The three renderer
paths that reach ``erase_down`` all move to column zero first, which is what makes the
replacement sound for them -- it is a precondition to enforce, not a property to assume, and
the replacement must not be installed unconditionally outside an active reservation.

``DL`` needs no knowledge of the cursor's row, which matters because ``Output`` does not track
one.

The region must be anchored at row 1. A region starting lower orphans the rows above it: they
never scroll and so never reach the terminal's scrollback.

Changing the margins moves the cursor. DECSTBM homes it, and so does the reset -- measured on
tmux 3.7c, where a cursor at row 10 landed at row 1 after each. Every margin change is
therefore wrapped in a save/restore pair (``ESC 7`` / ``ESC 8``), or entering the region below
existing output would send later rendering to the top of the screen and overwrite it.

The caller is responsible for the cursor not being inside the reserved band when the region is
established: this helper cannot discover the cursor's row without a cursor-position report,
which needs input it does not have. Placing the prompt within the usable area belongs to the
layer that owns the terminal.

A region needs at least two usable rows. DECSTBM requires the bottom margin to be greater
than the top, so a degenerate ``ESC [ 1 ; 1 r`` is ignored and the terminal silently keeps
its previous margins -- measured on tmux 3.7c, where output then scrolled through the
reserved row and destroyed it. The failure is total rather than degraded, so callers must
release the reservation below this floor rather than narrow it.
"""

from types import TracebackType
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from prompt_toolkit.output import Output

#: Smallest region a terminal will honour. ``ESC [ 1 ; 1 r`` is ignored outright.
MIN_USABLE_ROWS = 2

#: Upper bound on the lines one ``DL`` may delete. Terminals clamp the count to the scroll
#: region, so any value at least as large as the tallest plausible terminal clears to the
#: bottom margin exactly.
_MAX_ROWS = 9999


def scroll_region_sequence(total_rows: int, reserved_rows: int) -> str:
    """Build the DECSTBM sequence reserving ``reserved_rows`` rows at the bottom.

    :param total_rows: height of the terminal in rows
    :param reserved_rows: number of bottom rows to keep out of the scroll region
    :return: the escape sequence setting the scroll region
    :raises ValueError: if the reservation would leave fewer than two usable rows
    """
    if reserved_rows < 1:
        raise ValueError(f"reserved_rows must be at least 1, got {reserved_rows}")
    usable = total_rows - reserved_rows
    if usable < MIN_USABLE_ROWS:
        raise ValueError(
            f"reserving {reserved_rows} of {total_rows} rows leaves {usable} usable row(s); "
            f"a scroll region needs at least {MIN_USABLE_ROWS}"
        )
    return f"\x1b[1;{usable}r"


def reset_scroll_region_sequence() -> str:
    """Build the sequence restoring full-screen scroll margins.

    :return: the escape sequence resetting the scroll region
    """
    return "\x1b[r"


def cursor_save_sequence() -> str:
    """Build the sequence saving the cursor position.

    :return: the DECSC escape sequence
    """
    return "\x1b7"


def cursor_restore_sequence() -> str:
    """Build the sequence restoring a saved cursor position.

    :return: the DECRC escape sequence
    """
    return "\x1b8"


def bounded_erase_screen_sequence(rows: int) -> str:
    """Build a margin-bounded replacement for ``ED2``.

    This is a deliberate contract rather than a reproduction of ``ED2``. ``ED2`` erases the
    display without moving the cursor -- ``Renderer.clear()`` homes it separately afterwards.
    The bounded form homes inside the region first because ``DL`` clears downward from the
    cursor, so reaching the whole usable area requires starting at its top. Callers therefore
    get an erase-and-home, which is what ``Renderer.clear()`` produces anyway.

    :param rows: number of usable rows to clear
    :return: the escape sequence clearing the usable region and homing within it
    """
    return f"\x1b[1;1H{bounded_erase_down_sequence(rows)}"


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
        self._previous: dict[str, Callable[[], None] | None] = {}

    @property
    def usable_rows(self) -> int:
        """Number of rows available to the application, excluding the reserved rows."""
        return self._total_rows - self._reserved_rows

    def _bounded_erase_down(self) -> None:
        """Erase from the cursor to the bottom margin, leaving the reserved rows intact."""
        self._output.write_raw(bounded_erase_down_sequence(self.usable_rows))

    def _bounded_erase_screen(self) -> None:
        """Erase the usable region and home within it, leaving the reserved rows intact.

        Homing is part of this contract; see :func:`bounded_erase_screen_sequence`.
        """
        self._output.write_raw(bounded_erase_screen_sequence(self.usable_rows))

    def _write_preserving_cursor(self, sequence: str) -> None:
        """Emit a margin change without moving the cursor.

        :param sequence: the margin sequence to emit
        """
        self._output.write_raw(f"{cursor_save_sequence()}{sequence}{cursor_restore_sequence()}")
        # write_raw only appends to the output's own buffer, so this has to reach the
        # terminal here rather than waiting for whatever flushes next.
        self._output.flush()

    def __enter__(self) -> Self:
        """Set the scroll region and install the bounded erase."""
        self._write_preserving_cursor(self._region_sequence)
        # Shadow the bound methods with instance attributes. setattr keeps this legible to
        # type checkers, which otherwise reject assigning over a method. Capture any
        # override already installed by a caller so exit can put it back rather than
        # leaving ours in place. Both destructive paths need bounding: the renderer's
        # erase() reaches erase_down, and its clear() -- Ctrl-L -- reaches erase_screen.
        for name, bounded in (
            ("erase_down", self._bounded_erase_down),
            ("erase_screen", self._bounded_erase_screen),
        ):
            self._previous[name] = vars(self._output).get(name)
            setattr(self._output, name, bounded)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore the original erase and full-screen scroll margins."""
        for name, previous in self._previous.items():
            if previous is None:
                delattr(self._output, name)  # fall back to the class implementation
            else:
                setattr(self._output, name, previous)
        self._previous.clear()
        # Restoration has to reach the terminal here. A body that exits without another
        # renderer operation -- an exception, or application shutdown -- would otherwise
        # leave the margins restricted and later shell output scrolling inside them.
        self._write_preserving_cursor(reset_scroll_region_sequence())
