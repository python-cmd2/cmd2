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

**Carriage returns are dropped and tabs are expanded.** Both are cursor motion in a context
where the painter owns the cursor.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.output import ColorDepth, Output
from prompt_toolkit.utils import get_cwidth

from .scroll_region import cursor_restore_sequence, cursor_save_sequence
from .terminal_transaction import TerminalLock, assert_no_terminal_transaction

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Mapping

    from prompt_toolkit.formatted_text import AnyFormattedText
    from prompt_toolkit.styles import Attrs, BaseStyle

    from .terminal_display import Geometry

#: Columns between tab stops. Tabs are expanded during layout because the painter positions
#: the cursor itself; letting a tab reach the terminal would move it by an amount the frame
#: does not model.
TAB_WIDTH = 8

#: Fragments whose style contains this carry raw terminal control rather than text.
_ZERO_WIDTH_ESCAPE = "[ZeroWidthEscape]"


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
        Content taller than the band is truncated here -- growing the toolbar is a geometry
        transition, and writing the extra rows would put them outside the reservation.

        :param content: the formatted text to lay out
        :param width: the terminal width in columns
        :param height: the height of the reserved band in rows
        :param default_style: the style for padding cells
        :return: the frame
        :raises ValueError: if ``width`` or ``height`` is not positive
        """
        if width < 1:
            raise ValueError(f"a frame needs a positive width, got {width}")
        if height < 1:
            raise ValueError(f"a frame needs a positive height, got {height}")

        rows = _layout(content, width, default_style)
        blank = tuple(Cell(" ", default_style) for _ in range(width))
        while len(rows) < height:
            rows.append(list(blank))
        return cls(rows=tuple(tuple(row) for row in rows[:height]))


def measure_toolbar_height(content: "AnyFormattedText", width: int) -> int:
    """Measure how many rows content needs at a given width.

    This is what sizes the reservation, so it counts wrapping and explicit newlines the same
    way :meth:`ToolbarFrame.build` lays them out. Empty content still measures one row: an
    empty toolbar is an intentional visibility change, not a request for no reservation.

    :param content: the formatted text to measure
    :param width: the terminal width in columns
    :return: the number of rows required, at least one
    :raises ValueError: if ``width`` is not positive
    """
    if width < 1:
        raise ValueError(f"measuring needs a positive width, got {width}")
    return max(1, len(_layout(content, width, "")))


def _layout(content: "AnyFormattedText", width: int, default_style: str) -> list[list[Cell]]:
    """Lay content out into as many full-width rows as it needs.

    :param content: the formatted text to lay out
    :param width: the terminal width in columns
    :param default_style: the style for padding cells
    :return: the rows, each padded to ``width`` cells
    """
    rows: list[list[Cell]] = []
    row: list[Cell] = []

    def finish_row() -> None:
        """Pad the row in progress and start a new one."""
        row.extend(Cell(" ", default_style) for _ in range(width - len(row)))
        rows.append(list(row))
        row.clear()

    for fragment in to_formatted_text(content):
        style, text = fragment[0], fragment[1]
        if _ZERO_WIDTH_ESCAPE in style:
            continue
        for char in text:
            if char == "\n":
                finish_row()
                continue
            if char == "\r":
                continue
            if char == "\t":
                spaces = TAB_WIDTH - (len(row) % TAB_WIDTH)
                for _ in range(spaces):
                    if len(row) == width:
                        finish_row()
                    row.append(Cell(" ", style))
                continue

            char_width = get_cwidth(char)
            if char_width == 0 and row and not row[-1].is_continuation:
                # A combining mark belongs to the character it follows; it occupies no column
                # of its own, so it joins that cell rather than becoming one.
                previous = row[-1]
                row[-1] = Cell(previous.char + char, previous.style)
                continue
            columns = max(1, char_width)
            if len(row) + columns > width:
                # Padding rather than splitting: half a wide character at the right edge is
                # what makes the terminal wrap the row itself, which would put toolbar cells
                # in a row the frame does not own.
                finish_row()
            row.append(Cell(char, style))
            if columns == 2:
                row.append(Cell("", style, is_continuation=True))

    if row:
        finish_row()
    return rows


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
        output: Output,
        lock: TerminalLock,
        style: "BaseStyle",
        color_depth: ColorDepth,
        default_style: str = "",
        autowrap_after_paint: bool = True,
    ) -> None:
        """Bind a painter to the physical backend.

        :param output: the *original* backend; the band is outside the application's geometry,
            so painting through the reserved adapter would be painting through a view that
            excludes it
        :param lock: the terminal transaction lock shared by all cmd2-controlled output
        :param style: the style rules used to resolve fragment styles
        :param color_depth: the color depth to render attributes at
        :param default_style: the style for padding cells
        :param autowrap_after_paint: the committed autowrap policy to restore afterwards.
            Upstream's renderer leaves autowrap enabled between frames, which is the default
            here; a bridge that has committed a different policy passes it instead.
        """
        self._output = output
        self._lock = lock
        self._style = style
        self._color_depth = color_depth
        self._default_style = default_style
        self._autowrap_after_paint = autowrap_after_paint
        self._last_frame: ToolbarFrame | None = None
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
        self._last_band = None

    def prepare(self, content: "Callable[[], AnyFormattedText]", width: int, height: int) -> PreparedFrame | None:
        """Evaluate the toolbar's content once and lay it out, off the terminal lock.

        :param content: the callback returning the toolbar's formatted text
        :param width: the terminal width in columns
        :param height: the height of the reserved band in rows
        :return: the prepared frame, or ``None`` if evaluation failed or is waiting on a report
        """
        assert_no_terminal_transaction("evaluating the toolbar's content")
        if self._pending_error is not None:
            return None
        try:
            text = content()
        except Exception as error:  # noqa: BLE001 - a toolbar callback must not end a command
            # The last good frame stays on screen. A toolbar that blanks itself because a
            # callback raised is a worse failure than a stale one, and the command that was
            # running is not this callback's to interrupt.
            self._pending_error = error
            return None
        frame = ToolbarFrame.build(text, width=width, height=height, default_style=self._default_style)
        styles = {cell.style for row in frame.rows for cell in row}
        return PreparedFrame(
            frame=frame,
            attrs={style: self._style.get_attrs_for_style_str(style) for style in styles},
            color_depth=self._color_depth,
        )

    def paint(self, prepared: PreparedFrame, geometry: "Geometry") -> bool:
        """Write the changed cells of the band, inside one terminal transaction.

        :param prepared: the frame to paint
        :param geometry: the geometry the band is positioned by
        :return: whether anything was written
        :raises ValueError: if the frame does not match the reserved band
        """
        frame = prepared.frame
        if frame.height != geometry.reserved_rows or frame.width != geometry.columns:
            raise ValueError(
                f"a {frame.height}x{frame.width} frame does not fit a {geometry.reserved_rows}x{geometry.columns} band"
            )

        band = (geometry.physical_rows, geometry.columns, geometry.reserved_rows, geometry.buffer_id)
        previous = self._last_frame if band == self._last_band else None
        runs = _changed_runs(previous, frame)
        if not runs:
            self._last_frame = frame
            self._last_band = band
            return False

        top_row = geometry.physical_rows - geometry.reserved_rows + 1
        with self._lock.transaction("paint", generation=geometry.generation):
            # Anything another writer left buffered goes out first, so the band is painted
            # after the output it was meant to follow rather than in the middle of it.
            self._output.flush()
            # DECSC saves the cursor *and* the current attributes, and DECRC restores both, so
            # the renderer's next write lands where and how it expects.
            self._output.write_raw(cursor_save_sequence())
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

        self._last_frame = frame
        self._last_band = band
        return True


def _cursor_position_sequence(row: int, column: int) -> str:
    """Build a one-based absolute cursor move.

    The band is addressed in physical coordinates, which the application's view does not
    contain, so this deliberately does not go through ``cursor_goto``.

    :param row: one-based physical row
    :param column: one-based column
    :return: the CUP escape sequence
    """
    return f"\x1b[{row};{column}H"


def _changed_runs(
    previous: ToolbarFrame | None,
    frame: ToolbarFrame,
) -> list[tuple[int, int, tuple[Cell, ...]]]:
    """Find the spans of cells that differ from what is believed to be on screen.

    A run always begins on a whole character: a wide character's two cells carry the same
    style and change together, so a difference can never start on the right half of one.

    :param previous: the frame believed to be displayed, or ``None`` for a full repaint
    :param frame: the frame to display
    :return: ``(row index, first column, cells)`` for each run, in order
    """
    runs: list[tuple[int, int, tuple[Cell, ...]]] = []
    for row_index, row in enumerate(frame.rows):
        previous_row = previous.rows[row_index] if previous is not None else None
        column = 0
        while column < len(row):
            if previous_row is not None and row[column] == previous_row[column]:
                column += 1
                continue
            start = column
            while column < len(row) and (previous_row is None or row[column] != previous_row[column]):
                column += 1
            # A wide character whose halves straddle the end of the run comes along whole.
            while column < len(row) and row[column].is_continuation:
                column += 1
            runs.append((row_index, start, tuple(row[start:column])))
    return runs
