"""A virtual :class:`~prompt_toolkit.output.Output` that hides the reserved rows.

The application renders through this adapter and sees a terminal one reservation shorter
than the real one. Everything it cannot reach is delegated to the backend unchanged.

Two rules shape the whole module.

**Explicit implementation, not ``__getattr__``.** ``Output`` is an abstract base class, so a
class that answers by attribute lookup alone is not instantiable and, worse, silently
acquires whatever a future prompt-toolkit adds without anyone deciding what the reservation
means for it. Every abstract method is written out here.

**The wrapped backend is never modified.** The earlier spike installed bounded erases by
assigning over the backend's bound methods, which made restoration a matter of putting the
right objects back in the right order and lost a caller's own override if one was already
there. Wrapping instead means the backend a caller handed in is byte-for-byte the object
they get back, whatever happened in between.

The bounded erases are only sound from column zero: ``ED`` preserves the cursor line's
prefix while ``DL`` deletes the whole line, and on tmux 3.7c a ``DL`` from a nonzero column
destroyed committed text to its left. All three renderer paths that reach ``erase_down``
move to column zero first, which is what makes the substitution valid for them -- a
precondition, not an assumption, and the reason the replacement lives on an adapter that
exists only while a reservation is installed rather than being installed on the backend
permanently.
"""

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import Output

from .scroll_region import bounded_erase_down_sequence, bounded_erase_screen_sequence

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.cursor_shapes import CursorShape
    from prompt_toolkit.output import ColorDepth
    from prompt_toolkit.styles import Attrs

    from .terminal_display import TerminalDisplay


class ReservedOutput(Output):
    """Presents the usable region of a reserved terminal as if it were the whole terminal."""

    #: Marks this object as an adapter so the physical layer can refuse to wrap it and read
    #: sizes that have already had the reservation subtracted once.
    is_reserved_adapter = True

    def __init__(self, wrapped: Output, display: "TerminalDisplay") -> None:
        """Wrap a backend for the duration of a reservation.

        :param wrapped: the original backend, which this object never modifies
        :param display: the owner of the current geometry
        """
        self._wrapped = wrapped
        self._display = display
        # A plain attribute rather than a property: Output declares stdout as writable, and
        # code that reaches for the real stream must find the backend's, not a copy of it.
        self.stdout = getattr(wrapped, "stdout", None)

    @property
    def wrapped(self) -> Output:
        """The backend being wrapped."""
        return self._wrapped

    @property
    def _usable_rows(self) -> int:
        """Height of the usable region for the current generation."""
        geometry = self._display.geometry
        if geometry is None:  # pragma: no cover - the adapter does not outlive its reservation
            return self._wrapped.get_size().rows
        return geometry.usable_rows

    # -- geometry -------------------------------------------------------------------------

    def get_size(self) -> Size:
        """Report the usable region as the terminal's size.

        :return: the virtual size, one reservation shorter than the physical terminal
        """
        geometry = self._display.geometry
        if geometry is None:  # pragma: no cover - the adapter does not outlive its reservation
            return self._wrapped.get_size()
        return geometry.virtual_size

    def get_rows_below_cursor_position(self) -> int:
        """Report the distance from the cursor to the bottom of the *usable* region.

        Windows answers this natively from viewport and cursor data, so adapting
        :meth:`get_size` alone would leave the renderer believing it can draw over the
        reserved rows. POSIX backends raise :class:`NotImplementedError` here, which is
        delegated unchanged so the renderer falls back to CPR exactly as it would have.

        :return: rows below the cursor within the usable region, never negative
        """
        below = self._wrapped.get_rows_below_cursor_position()
        geometry = self._display.geometry
        if geometry is None:  # pragma: no cover - the adapter does not outlive its reservation
            return below
        return max(0, below - geometry.reserved_rows)

    # -- erases ---------------------------------------------------------------------------

    def erase_down(self) -> None:
        """Clear from the cursor to the bottom margin, leaving the reserved rows intact."""
        self._wrapped.write_raw(bounded_erase_down_sequence(self._usable_rows))

    def erase_screen(self) -> None:
        """Clear the usable region and home within it, leaving the reserved rows intact.

        Homing is part of the contract rather than an extra: ``DL`` clears downward from the
        cursor, so covering the whole usable area means starting at its top. ``Renderer.clear()``
        homes immediately afterwards anyway, which is the path Ctrl-L takes.
        """
        self._wrapped.write_raw(bounded_erase_screen_sequence(self._usable_rows))

    def erase_end_of_line(self) -> None:
        """Clear to the end of the current line, which is bounded by the line already."""
        self._wrapped.erase_end_of_line()

    # -- screen buffers -------------------------------------------------------------------

    def enter_alternate_screen(self) -> None:
        """Hand the terminal over to the alternate buffer with full margins restored.

        The two buffers keep separate margin state, and the application taking over knows
        nothing about a reservation. Margins are restored before the switch so the main
        buffer is left in the state the shell expects if the switch is never undone.
        """
        self._display.release_region_for_handoff()
        self._wrapped.enter_alternate_screen()

    def quit_alternate_screen(self) -> None:
        """Return to the main buffer and re-establish the reservation for its geometry."""
        self._wrapped.quit_alternate_screen()
        self._display.reacquire_region_after_handoff()

    def scroll_buffer_to_prompt(self) -> None:
        """Scroll the Windows viewport to the prompt, then re-check the viewport origin.

        This can move the viewport, and a moved viewport makes absolute row numbers address
        different cells even when width and height are unchanged, so the geometry generation
        has to be revalidated afterwards rather than assumed still current.
        """
        self._wrapped.scroll_buffer_to_prompt()
        self._display.revalidate_viewport()

    # -- straight delegation --------------------------------------------------------------

    def fileno(self) -> int:
        """Return the file descriptor of the underlying backend."""
        return self._wrapped.fileno()

    def encoding(self) -> str:
        """Return the backend's encoding."""
        return self._wrapped.encoding()

    def write(self, data: str) -> None:
        """Write text through the backend.

        :param data: the text to write
        """
        self._wrapped.write(data)

    def write_raw(self, data: str) -> None:
        """Write unescaped data through the backend.

        :param data: the raw data to write
        """
        self._wrapped.write_raw(data)

    def set_title(self, title: str) -> None:
        """Set the terminal title.

        :param title: the title to set
        """
        self._wrapped.set_title(title)

    def clear_title(self) -> None:
        """Clear the terminal title."""
        self._wrapped.clear_title()

    def flush(self) -> None:
        """Flush the backend's buffer.

        This calls the backend's own ``flush``, which on Windows enables VT processing for
        the write and restores the previous console mode afterwards. Flushing its inner VT
        object directly would skip that.
        """
        self._wrapped.flush()

    def set_attributes(self, attrs: "Attrs", color_depth: "ColorDepth") -> None:
        """Apply text attributes.

        :param attrs: the attributes to apply
        :param color_depth: the color depth to render them at
        """
        self._wrapped.set_attributes(attrs, color_depth)

    def reset_attributes(self) -> None:
        """Reset text attributes to their defaults."""
        self._wrapped.reset_attributes()

    def disable_autowrap(self) -> None:
        """Turn off automatic line wrapping."""
        self._wrapped.disable_autowrap()

    def enable_autowrap(self) -> None:
        """Turn on automatic line wrapping."""
        self._wrapped.enable_autowrap()

    def cursor_goto(self, row: int = 0, column: int = 0) -> None:
        """Move the cursor to a position within the usable region.

        :param row: zero-based row, as prompt-toolkit counts them
        :param column: zero-based column
        """
        self._wrapped.cursor_goto(row, column)

    def cursor_up(self, amount: int) -> None:
        """Move the cursor up.

        :param amount: rows to move
        """
        self._wrapped.cursor_up(amount)

    def cursor_down(self, amount: int) -> None:
        """Move the cursor down.

        :param amount: rows to move
        """
        self._wrapped.cursor_down(amount)

    def cursor_forward(self, amount: int) -> None:
        """Move the cursor right.

        :param amount: columns to move
        """
        self._wrapped.cursor_forward(amount)

    def cursor_backward(self, amount: int) -> None:
        """Move the cursor left.

        :param amount: columns to move
        """
        self._wrapped.cursor_backward(amount)

    def hide_cursor(self) -> None:
        """Hide the cursor."""
        self._wrapped.hide_cursor()

    def show_cursor(self) -> None:
        """Show the cursor."""
        self._wrapped.show_cursor()

    def set_cursor_shape(self, cursor_shape: "CursorShape") -> None:
        """Set the cursor shape.

        :param cursor_shape: the shape to set
        """
        self._wrapped.set_cursor_shape(cursor_shape)

    def reset_cursor_shape(self) -> None:
        """Restore the default cursor shape."""
        self._wrapped.reset_cursor_shape()

    def enable_mouse_support(self) -> None:
        """Turn on mouse reporting."""
        self._wrapped.enable_mouse_support()

    def disable_mouse_support(self) -> None:
        """Turn off mouse reporting."""
        self._wrapped.disable_mouse_support()

    def enable_bracketed_paste(self) -> None:
        """Turn on bracketed paste."""
        self._wrapped.enable_bracketed_paste()

    def disable_bracketed_paste(self) -> None:
        """Turn off bracketed paste."""
        self._wrapped.disable_bracketed_paste()

    def reset_cursor_key_mode(self) -> None:
        """Restore the default cursor-key mode."""
        self._wrapped.reset_cursor_key_mode()

    def ask_for_cpr(self) -> None:
        """Ask the terminal for a cursor-position report.

        The reply comes back in *physical* coordinates while the renderer compares it against
        the virtual height. That arithmetic is correct only because the region is anchored at
        row 1, which makes the usable height the last usable physical row index as well.
        Validating the reply against the band belongs to the bridge, in Stage 2b.
        """
        self._wrapped.ask_for_cpr()

    @property
    def responds_to_cpr(self) -> bool:
        """Whether the backend answers cursor-position reports."""
        return self._wrapped.responds_to_cpr

    def bell(self) -> None:
        """Sound the terminal bell."""
        self._wrapped.bell()

    def get_default_color_depth(self) -> "ColorDepth":
        """Return the backend's default color depth."""
        return self._wrapped.get_default_color_depth()
