"""Lay toolbar content out as display cells and paint only what changed.

The toolbar in reserved mode is not a prompt-toolkit window. It is painted independently into
rows the application cannot reach, which is what keeps it out of the renderer's diff and out
of its erases -- and it is why the layout work upstream would have done has to be done here.

A :class:`ToolbarFrame` is a grid of what the terminal will *show*: one :class:`Cell` per
display column, per row of the band. Comparing two frames therefore answers "will the user see
a difference", not "did the Python string change", which is the comparison that decides
whether anything is emitted at all. A wide character owns two cells, a combining character
owns none of its own, and a wide character is never split across the right edge -- half a
character at the edge is what makes a terminal wrap a row into the one below it.

Content is laid out rather than passed through:

**Zero-width escape fragments are dropped.** ``[ZeroWidthEscape]`` fragments carry raw
terminal control, and arbitrary control inside a paint moves the physical cursor out of the
band and into the application's rows.

**Mouse handlers are dropped, text and style are kept.** The band is outside prompt-toolkit's
mouse map, so a handler here would never be called; rendering the visible part is the honest
subset rather than advertising support that does not exist.

**Lines are clipped with an ellipsis.** Newlines advance to the next reserved row;
horizontal overflow never wraps. Omitted columns or rows are indicated at the right edge,
but only when something visible was omitted: trailing whitespace and a trailing newline
overflow by nothing the user could have seen.

**Carriage returns are dropped and tabs are expanded.** Both are cursor motion in a context
where the painter owns the cursor.

**Control characters are shown, not sent.** An escape becomes ``^[`` and a C1 control
becomes ``<85>``, exactly as the renderer shows them, so a stray sequence in a plain string
is displayed inside the band rather than executed there.
"""

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.utils import get_cwidth

from .scroll_region import cursor_restore_sequence, cursor_save_sequence
from .terminal_transaction import TerminalLock, assert_no_terminal_transaction

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Mapping

    from prompt_toolkit.formatted_text import AnyFormattedText, StyleAndTextTuples
    from prompt_toolkit.styles import Attrs, BaseStyle

    from .terminal_display import TerminalDisplay

#: Columns between tab stops. Tabs are expanded during layout because the painter positions
#: the cursor itself; letting a tab reach the terminal would move it by an amount the frame
#: does not model.
TAB_WIDTH = 8

#: What marks omitted content in the rightmost column of a row. U+2026 is East-Asian-ambiguous
#: width: prompt-toolkit measures it as one column, and so does every terminal cmd2 is
#: qualified on, but a terminal configured to draw ambiguous characters two columns wide would
#: draw this one over the edge. There is no portable way to detect that configuration, so the
#: glyph is a constant an application can replace rather than a value the painter guesses.
TRUNCATION_INDICATOR = "…"

#: Fragments whose style contains this carry raw terminal control rather than text.
_ZERO_WIDTH_ESCAPE = "[ZeroWidthEscape]"

#: The style class the renderer gives a control character's caret notation, so that a theme
#: styling ``^[`` in a prompt styles it the same way in the band.
_CONTROL_STYLE = "class:control-character"

#: Characters that occupy a column without showing anything. A tab is expanded to these and a
#: carriage return is dropped, so past the right edge all three are the same: nothing lost.
_BLANK = " \t\r"


@dataclass(frozen=True)
class Cell:
    """One display column of the toolbar band."""

    #: What is drawn here: a character, a character plus its combining marks, or ``""`` for
    #: the second half of a wide character and for a blank continuation cell.
    char: str

    #: The style string that applies to this column.
    style: str

    #: Whether this cell is the right half of a wide character in the cell before it.
    is_continuation: bool = False

    @property
    def width(self) -> int:
        """How many columns this cell's content occupies: two for a wide character, else one."""
        if self.is_continuation:
            return 0
        return get_cwidth(self.char)


@dataclass(frozen=True)
class ToolbarFrame:
    """An immutable grid of cells: exactly ``height`` rows of exactly ``width`` cells."""

    #: The rows of the band, top first.
    rows: tuple[tuple[Cell, ...], ...]

    @property
    def height(self) -> int:
        """How many rows the frame occupies."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """How many columns each row occupies."""
        return len(self.rows[0]) if self.rows else 0

    @classmethod
    def build(
        cls,
        content: "AnyFormattedText",
        width: int,
        height: int,
        default_style: str = "",
    ) -> "ToolbarFrame":
        """Lay content out into a frame of exactly ``height`` by ``width`` cells.

        Content that does not fill the frame is padded with default-styled spaces: the pad is
        what overwrites a longer previous frame, so it is content rather than absence of it.
        Each logical line is clipped to the terminal width without wrapping. A right-edge
        ellipsis marks omitted columns, or omitted lines on the last reserved row -- but only
        when what was omitted would have been visible. Trailing spaces, a trailing tab and a
        trailing newline overflow by nothing anyone can see, and marking them would replace a
        real character to announce that nothing was lost. Growing the toolbar is a geometry
        transition, never a consequence of content overflow.

        :param content: the formatted text to lay out
        :param width: the terminal width in columns
        :param height: the height of the reserved band in rows
        :param default_style: the style for padding and truncation-indicator cells
        :return: the frame
        :raises ValueError: if ``width`` or ``height`` is not positive
        """
        if width < 1:
            raise ValueError(f"a frame needs a positive width, got {width}")
        if height < 1:
            raise ValueError(f"a frame needs a positive height, got {height}")

        # One pad cell shared by every blank column. Cells are immutable and compared by
        # value, and this runs on every refresh, where constructing one per column was most
        # of the cost of laying out a short toolbar.
        pad = Cell(" ", default_style)
        lines = list(split_lines(to_formatted_text(content)))
        rows: list[list[Cell]] = []
        for line in lines[:height]:
            row, clipped = _clip_line(line, width, pad)
            if clipped:
                _mark_truncated(row, default_style)
            rows.append(row)
        if any(_has_visible_text(line) for line in lines[height:]):
            _mark_truncated(rows[-1], default_style)
        while len(rows) < height:
            rows.append([pad] * width)
        return cls(rows=tuple(tuple(row) for row in rows))


def _mark_truncated(row: list[Cell], default_style: str) -> None:
    """Mark omitted content in the rightmost column without splitting a wide character.

    :param row: a padded, nonempty row to modify
    :param default_style: the style for the indicator and any cleared wide-character cell
    """
    if row[-1].is_continuation:
        row[-2] = Cell(" ", default_style)
    row[-1] = Cell(TRUNCATION_INDICATOR, default_style)


def _displayed(char: str, style: str) -> tuple[str, str]:
    """Decide what the terminal is shown for one character of content.

    Control characters are shown in the caret notation the renderer uses -- ``^[`` for an
    escape, ``<85>`` for a C1 control -- rather than written to the terminal, where an escape
    would be executed inside the band. A C1 control is a sequence introducer on many
    terminals, so it is as dangerous as ``ESC`` and mapped the same way.

    :param char: the character from the content
    :param style: the fragment's style
    :return: the text to draw and the style to draw it in
    """
    mapped = Char.display_mappings.get(char)
    if mapped is None:
        return char, style
    return mapped, f"{style} {_CONTROL_STYLE}".strip()


def _has_visible_text(line: "StyleAndTextTuples") -> bool:
    """Decide whether a logical line would show anything at all.

    :param line: the line's fragments
    :return: whether any character occupies a column with something in it
    """
    for fragment in line:
        style, text = fragment[0], fragment[1]
        if _ZERO_WIDTH_ESCAPE in style:
            continue
        for char in text:
            if char in _BLANK:
                continue
            shown, _ = _displayed(char, style)
            if any(piece not in _BLANK and get_cwidth(piece) > 0 for piece in shown):
                return True
    return False


def _clip_line(line: "StyleAndTextTuples", width: int, pad: Cell) -> tuple[list[Cell], bool]:
    """Lay one logical line out as a padded row, stopping at the first visible character lost.

    :param line: the line's fragments
    :param width: the terminal width in columns
    :param pad: the cell that fills columns the content does not reach
    :return: the row, and whether visible content was clipped from it
    """
    row: list[Cell] = []
    # Whether a character has been dropped past the right edge. A combining mark that
    # follows one belongs to it, not to whatever cell happens to be last.
    dropped = False

    for fragment in line:
        style, text = fragment[0], fragment[1]
        if _ZERO_WIDTH_ESCAPE in style:
            continue
        for char in text:
            if char == "\r":
                continue
            if char == "\t":
                available = width - len(row)
                if available <= 0:
                    dropped = True
                    continue
                spaces = TAB_WIDTH - (len(row) % TAB_WIDTH)
                row.extend([Cell(" ", style)] * min(spaces, available))
                continue

            shown, cell_style = _displayed(char, style)
            for piece in shown:
                piece_width = get_cwidth(piece)
                if piece_width == 0:
                    if dropped:
                        # Its base is gone; attaching it to the last retained cell would
                        # decorate a character it was never part of.
                        continue
                    if row:
                        base = len(row) - 1
                        if row[base].is_continuation:
                            base -= 1
                        previous = row[base]
                        row[base] = Cell(previous.char + piece, previous.style, previous.is_continuation)
                    else:
                        # Nothing to combine with. Drawn on a space so that it occupies the
                        # one column the terminal gives it; a cell of its own would be
                        # modelled at a column the terminal never advances past.
                        row.append(Cell(" " + piece, cell_style))
                    continue
                columns = max(1, piece_width)
                if len(row) + columns > width:
                    dropped = True
                    if piece in _BLANK:
                        continue
                    # Visible content is lost from here on, and nothing after it can be
                    # shown, so there is no reason to look at the rest of the line.
                    row.extend([pad] * (width - len(row)))
                    return row, True
                row.append(Cell(piece, cell_style))
                if columns == 2:
                    row.append(Cell("", cell_style, is_continuation=True))

    row.extend([pad] * (width - len(row)))
    return row, False


@dataclass(frozen=True)
class PreparedFrame:
    """A frame with every style already resolved, ready to emit.

    Style resolution runs application-supplied style rules, so it happens here -- during
    preparation, off the terminal lock -- rather than between two writes to the band.
    """

    #: The cells to paint.
    frame: ToolbarFrame

    #: Resolved attributes for every style string the frame uses.
    attrs: "Mapping[str, Attrs]"

    #: The color depth those attributes are rendered at.
    color_depth: ColorDepth

    #: The geometry generation the frame was laid out for. The band's physical rows come
    #: from this snapshot, so emitting the frame against any other one writes into rows the
    #: application now owns.
    generation: int


class ToolbarPainter:
    """Paints the reserved band, writing only the cells that changed.

    The painter is independent of the renderer: it writes to physical rows the application's
    geometry excludes, so its output is never part of a renderer diff and never erased by one.
    That independence is the whole mechanism, and it is also why the painter has to restore
    everything it touches -- the renderer's next frame assumes the cursor, attributes and wrap
    mode are where it left them.

    Nothing is erased before writing. An erase followed by a write is two visible states, and
    the flicker of that pair is what this design exists to remove; a changed run is overwritten
    in place and a shortened frame's tail is padded, which is one state.
    """

    def __init__(
        self,
        display: "TerminalDisplay",
        lock: TerminalLock,
        style: "BaseStyle",
        color_depth: ColorDepth,
        default_style: str = "",
        autowrap_after_paint: bool = True,
    ) -> None:
        """Bind a painter to the display that owns the reservation.

        The painter takes the display rather than an output and a geometry. The band's rows
        are physical, so a frame laid out for one geometry addresses the wrong rows under any
        other -- and a caller that passes both an output and a snapshot can pass a stale one.
        Reading the geometry from its owner, inside the transaction, removes that possibility.

        Painting goes to the *original* backend: the band is outside the application's
        geometry, so the reserved adapter is a view that excludes it.

        :param display: the owner of the reservation and its geometry
        :param lock: the terminal transaction lock shared by all cmd2-controlled output
        :param style: the style rules used to resolve fragment styles
        :param color_depth: the color depth to render attributes at
        :param default_style: the style for padding and truncation-indicator cells
        :param autowrap_after_paint: the committed autowrap policy to restore afterwards.
            Upstream's renderer leaves autowrap enabled between frames, which is the default
            here; a bridge that has committed a different policy passes it instead.
        """
        self._display = display
        self._output = display.terminal.output
        self._lock = lock
        self._style = style
        self._color_depth = color_depth
        self._default_style = default_style
        self._autowrap_after_paint = autowrap_after_paint
        self._last_frame: ToolbarFrame | None = None
        self._last_attrs: Mapping[str, Attrs] | None = None
        self._last_band: tuple[int, int, int, object] | None = None
        self._pending_error: BaseException | None = None

    @property
    def last_frame(self) -> ToolbarFrame | None:
        """The frame currently believed to be on the screen, or ``None`` after invalidation."""
        return self._last_frame

    def take_pending_error(self) -> BaseException | None:
        """Take the unreported content-callback error, if there is one.

        Taking it is what re-arms evaluation: until the user has been told, retrying the same
        failing callback on every refresh would report the same error forever.

        :return: the error to report once, or ``None``
        """
        error, self._pending_error = self._pending_error, None
        return error

    def invalidate(self) -> None:
        """Forget what is on the screen, so the next paint writes the whole band.

        Recovery, a geometry change and a handoff all leave the band's contents unknown. A
        diff against a frame that may no longer be displayed would write nothing at all.
        """
        self._last_frame = None
        self._last_attrs = None
        self._last_band = None

    def prepare(self, content: "Callable[[], AnyFormattedText]") -> PreparedFrame | None:
        """Evaluate the toolbar's content once and lay it out, off the terminal lock.

        :param content: the callback returning the toolbar's formatted text
        :return: the prepared frame, or ``None`` if there is no reservation to paint, or
            evaluation failed, or a previous failure is still waiting to be reported
        """
        assert_no_terminal_transaction("evaluating the toolbar's content")
        if self._pending_error is not None:
            return None
        geometry = self._display.geometry
        if geometry is None:
            return None
        try:
            text = content()
        except Exception as error:  # noqa: BLE001 - a toolbar callback must not end a command
            # The last good frame stays on screen. A toolbar that blanks itself because a
            # callback raised is a worse failure than a stale one, and the command that was
            # running is not this callback's to interrupt.
            self._pending_error = error
            return None
        frame = ToolbarFrame.build(
            text,
            width=geometry.columns,
            height=geometry.reserved_rows,
            default_style=self._default_style,
        )
        styles = {cell.style for row in frame.rows for cell in row}
        return PreparedFrame(
            frame=frame,
            attrs={style: self._style.get_attrs_for_style_str(style) for style in styles},
            color_depth=self._color_depth,
            generation=geometry.generation,
        )

    def paint(self, prepared: PreparedFrame) -> bool:
        """Write the changed cells of the band, inside one terminal transaction.

        The geometry is read from its owner *inside* the transaction and checked against the
        one the frame was laid out for. Between preparing and painting the terminal can be
        resized, released, or handed to another program, and each of those makes the band's
        physical rows rows the application owns instead. A refused frame publishes no
        baseline: what the band is showing is then unknown, so the next paint must be full.

        :param prepared: the frame to paint
        :return: whether anything was written
        """
        with self._lock.transaction("paint", generation=prepared.generation):
            geometry = self._display.geometry
            if geometry is None or geometry.generation != prepared.generation:
                self.invalidate()
                return False

            frame = prepared.frame
            band = (geometry.physical_rows, geometry.columns, geometry.reserved_rows, geometry.buffer_id)
            previous = self._last_frame if band == self._last_band else None
            previous_attrs = self._last_attrs if previous is not None else None
            runs = _changed_runs(previous, previous_attrs, frame, prepared.attrs)
            if not runs:
                self._last_frame = frame
                self._last_attrs = prepared.attrs
                self._last_band = band
                return False

            top_row = geometry.physical_rows - geometry.reserved_rows + 1
            # Whether *this* paint has saved the cursor yet. The opening flush belongs to
            # whoever wrote before us, and a failure there is not a partial paint.
            saved_cursor = False
            try:
                # Anything another writer left buffered goes out first, so the band is painted
                # after the output it was meant to follow rather than in the middle of it.
                self._output.flush()
                # DECSC saves the cursor *and* the current attributes, and DECRC restores
                # both, so the renderer's next write lands where and how it expects.
                self._output.write_raw(cursor_save_sequence())
                saved_cursor = True
                self._output.disable_autowrap()
                for row_index, column, cells in runs:
                    self._output.write_raw(_cursor_position_sequence(top_row + row_index, column + 1))
                    style: str | None = None
                    for cell in cells:
                        if cell.is_continuation:
                            continue
                        if cell.style != style:
                            self._output.set_attributes(prepared.attrs[cell.style], prepared.color_depth)
                            style = cell.style
                        self._output.write(cell.char)
                if self._autowrap_after_paint:
                    self._output.enable_autowrap()
                self._output.write_raw(cursor_restore_sequence())
                self._output.flush()
            except BaseException:
                self._recover_from_failed_paint(saved_cursor)
                raise

            self._last_frame = frame
            self._last_attrs = prepared.attrs
            self._last_band = band
            return True

    def _recover_from_failed_paint(self, saved_cursor: bool) -> None:
        """Undo what a half-finished paint left on the terminal.

        The backend buffers a paint and flushes it as one write, so a failure part-way through
        that write leaves the terminal holding a prefix: the cursor saved and moved into the
        band, autowrap off, some cells replaced and some not. None of that is undone by
        unwinding the Python call -- the sequences are already on the wire.

        Two things follow. The wrap mode and cursor are put back, because leaving autowrap off
        makes the next ordinary line of output wrap where it should not, and leaving the cursor
        in the band makes the next write land in the toolbar. And the baseline is discarded:
        the band is now showing something no frame describes, so the next paint has to be a
        full one rather than a diff against a frame that was never finished.

        None of it applies when the paint failed before saving the cursor. The opening flush
        drains whatever another writer left buffered, and a failure there belongs to that
        output, not to this paint: the terminal's saved position is still the one some earlier
        operation put there -- the margin change's, most likely -- and restoring it would move
        the cursor backwards over output written since, which the next write would overwrite.
        An old saved position is not a recovery origin.

        The restoration is itself a write to a terminal that has just failed one, so its own
        failure is suppressed -- the original is the one worth propagating.

        :param saved_cursor: whether this paint got as far as saving the cursor
        """
        self.invalidate()
        if not saved_cursor:
            return
        with suppress(Exception):
            if self._autowrap_after_paint:
                self._output.enable_autowrap()
            # DECRC returns to whatever was last saved. After a partial batch that is either
            # this paint's own save or the one the margin change made, so the cursor lands
            # somewhere known rather than wherever the truncated write stopped.
            self._output.write_raw(cursor_restore_sequence())
            self._output.flush()


def _cursor_position_sequence(row: int, column: int) -> str:
    """Build a one-based absolute cursor move.

    The band is addressed in physical coordinates, which the application's view does not
    contain, so this deliberately does not go through ``cursor_goto``.

    :param row: one-based physical row
    :param column: one-based column
    :return: the CUP escape sequence
    """
    return f"\x1b[{row};{column}H"


def _same_cell(
    old: Cell,
    old_attrs: "Mapping[str, Attrs]",
    new: Cell,
    new_attrs: "Mapping[str, Attrs]",
) -> bool:
    """Decide whether two cells would look identical on the terminal.

    Style *strings* are not enough. A style rule can be changed under a class name -- a theme
    switch, a dynamic style -- leaving ``class:status`` naming a different colour than it did
    last frame. Comparing the resolved attributes is what makes the comparison a question
    about the screen rather than about the text of the style.

    :param old: the cell believed to be displayed
    :param old_attrs: resolved attributes as they were when it was painted
    :param new: the cell to display
    :param new_attrs: resolved attributes for the new frame
    :return: whether the terminal would show the same thing
    """
    if old.char != new.char or old.is_continuation != new.is_continuation:
        return False
    return old_attrs.get(old.style) == new_attrs.get(new.style)


def _changed_runs(
    previous: ToolbarFrame | None,
    previous_attrs: "Mapping[str, Attrs] | None",
    frame: ToolbarFrame,
    attrs: "Mapping[str, Attrs]",
) -> list[tuple[int, int, tuple[Cell, ...]]]:
    """Find the spans of cells that differ from what is believed to be on screen.

    A run always begins on a whole character: a wide character's two cells carry the same
    style and change together, so a difference can never start on the right half of one.

    :param previous: the frame believed to be displayed, or ``None`` for a full repaint
    :param previous_attrs: the attributes that frame was painted with
    :param frame: the frame to display
    :param attrs: resolved attributes for the frame to display
    :return: ``(row index, first column, cells)`` for each run, in order
    """
    runs: list[tuple[int, int, tuple[Cell, ...]]] = []
    old_attrs: Mapping[str, Attrs] = previous_attrs if previous_attrs is not None else {}
    for row_index, row in enumerate(frame.rows):
        previous_row = previous.rows[row_index] if previous is not None else None
        column = 0
        while column < len(row):
            if previous_row is not None and _same_cell(previous_row[column], old_attrs, row[column], attrs):
                column += 1
                continue
            start = column
            while column < len(row) and (
                previous_row is None or not _same_cell(previous_row[column], old_attrs, row[column], attrs)
            ):
                column += 1
            # A wide character whose halves straddle the end of the run comes along whole.
            while column < len(row) and row[column].is_continuation:
                column += 1
            runs.append((row_index, start, tuple(row[start:column])))
    return runs
