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
from prompt_toolkit.utils import get_cwidth

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.formatted_text import AnyFormattedText

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
