"""A pager view hosted by the main prompt-toolkit application."""

import re
import threading
from array import array
from collections.abc import Callable
from functools import lru_cache, partial
from itertools import accumulate

from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_focus, is_searching, to_filter
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings import search
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl, UIContent
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.search import SearchDirection, start_search
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import SearchToolbar, TextArea

_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
# A sequence which sets the style of the text after it. It begins with characters which can
# be searched for quickly, which matters in a text with one or more of these on every line.
_SGR_RE = re.compile(r"\x1b\[[0-9;]*m")
# Everything else prompt-toolkit's ANSI parser takes out of the text, in the order it reads.
_OTHER_ESCAPE_RE = re.compile(
    # A style sequence which begins with the one-character introducer.
    r"\x9b[0-9;]*m"
    # Any other control sequence, or one the text ends in the middle of.
    r"|(?:\x1b\[|\x9b)[0-9;]*(?:[^0-9;m]|\Z)"
    # An escape which begins no control sequence, and the character after it.
    r"|\x1b(?:[^\[]|\Z)"
    # Readline's zero-width markers and what is between them.
    r"|\x01[^\x02]*(?:\x02|\Z)"
)
_RESETS = ("\x1b[0m", "\x1b[m")
# How many lines keep their fragments. A screen shows far fewer.
_PARSED_LINES = 1024


def _other_escape(match: re.Match[str]) -> str:
    """Return what prompt-toolkit's parser leaves in the text for an escape which sets no style."""
    sequence = match.group()
    if sequence[0] == "\x9b" and sequence[-1] == "m":
        return "\x1b[" + sequence[1:]
    if sequence[0] != "\x01" and sequence[-1] == "C":
        # Cursor forward is written as that many spaces.
        count = sequence[2:-1] if sequence[0] == "\x1b" else sequence[1:-1]
        return " " * min(int(count.split(";")[0] or 0), 9999)
    return ""


def _styled_and_plain(text: str) -> tuple[str, str]:
    """Return captured output with no escapes but those which set styles, and with none at all.

    Both drop the trailing newline which ends the last line.
    """
    # prompt-toolkit's ANSI parser does not handle OSC sequences, including Rich
    # hyperlinks. Remove their metadata while retaining visible text and SGR styles.
    styled = _OSC_RE.sub("", text).removesuffix("\n")
    plain = _SGR_RE.sub("", styled)
    if "\x1b" in plain or "\x9b" in plain or "\x01" in plain:
        # Rare, and slow to look for, so not looked for until there is one.
        styled = _OTHER_ESCAPE_RE.sub(_other_escape, styled)
        plain = _SGR_RE.sub("", styled)
    return styled, plain


def output_fits(text: str, columns: int, rows: int, *, chop: bool) -> bool:
    """Check rendered line heights, including wrapping and wide Unicode characters.

    Measuring the text itself keeps output that needs no scrolling from paying for a
    Pager's widgets and key bindings, which would only be built to be thrown away.
    """
    plain = _styled_and_plain(text)[1]
    if plain.count("\n") >= rows:
        # Every line takes a row at least, so no line needs to be measured.
        return False
    lines = plain.split("\n")
    if chop:
        # Even one wide line needs a pager so its hidden columns remain
        # accessible through horizontal scrolling.
        return all(get_cwidth(line) <= columns for line in lines)
    # Reuse prompt-toolkit's own wrapping arithmetic so this matches what a Pager
    # would render, without building a control to ask on the UI thread.
    content = UIContent(get_line=lambda number: [("", lines[number])], line_count=len(lines))
    height = 0
    for line in range(content.line_count):
        height += content.get_height_for_line(line, columns, None)
        if height > rows:
            return False
    return True


class _AnsiLexer(Lexer):
    """Preserve captured Rich styles while searching and scrolling plain text.

    prompt-toolkit's ANSI parser makes a fragment of every character, which for a long text
    takes seconds and hundreds of bytes for each character. So a line is parsed when it is
    asked for, which is when it is about to be shown.
    """

    def __init__(self, styled: str) -> None:
        """Keep the text to parse lines of.

        :param styled: the text, with no escape sequences except those which set styles
        """
        self._styled = styled
        self._lines = styled.split("\n")
        # Where each line starts in the text, to find the styles still in effect there. Left
        # empty for a text with no styles.
        self._starts = array("Q")
        if "\x1b" in styled:
            self._starts = array("Q", accumulate(map(len, self._lines), lambda start, length: start + length + 1, initial=0))
        self._parsed = lru_cache(maxsize=_PARSED_LINES)(self._parse)

    def _parse(self, number: int) -> StyleAndTextTuples:
        return to_formatted_text(ANSI(self._styles_in_effect(number) + self._lines[number]))

    def _styles_in_effect(self, number: int) -> str:
        """Return the sequences which set the style a line starts in.

        Those are the ones since the text was last reset to no style. Rich resets after each
        piece of text it styles, so in its output nothing is in effect when a line starts.
        """
        if not self._starts:
            return ""
        start = self._starts[number]
        since = 0
        for reset in _RESETS:
            found = self._styled.rfind(reset, since, start)
            if found != -1:
                since = found + len(reset)
        return "".join(_SGR_RE.findall(self._styled, since, start))

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:  # noqa: ARG002
        def get_line(number: int) -> StyleAndTextTuples:
            return self._parsed(number) if number < len(self._lines) else []

        return get_line


class Pager:
    """Scrollable, searchable output; the host supplies the persistent toolbar."""

    def __init__(self, text: str, *, chop: bool) -> None:
        """Build an independent view without creating an application or input reader."""
        self.closed = threading.Event()
        self.on_close: Callable[[], None] = self.closed.set
        self.chop = chop
        styled, plain = _styled_and_plain(text)
        self.search = SearchToolbar()
        self.text = TextArea(
            text=plain,
            lexer=_AnsiLexer(styled),
            read_only=True,
            wrap_lines=not chop,
            search_field=self.search,
        )
        self.text.window.always_hide_cursor = to_filter(True)
        self.container = HSplit(
            [
                self.text,
                self.search,
                ConditionalContainer(
                    Window(
                        FormattedTextControl(" Space/PgDn: next  b/PgUp: back  /: search  n: next match  q: quit"),
                        height=1,
                        style="class:bottom-toolbar",
                    ),
                    filter=~is_searching,
                ),
            ]
        )
        self.bindings = bindings = KeyBindings()
        focused = has_focus(self.text)

        @bindings.add("<any>", filter=focused)
        def ignore(event: KeyPressEvent) -> None:
            # Pager keystrokes must not become commands at the next prompt.
            pass

        @bindings.add("q", filter=focused)
        @bindings.add("escape", filter=focused, eager=True)
        @bindings.add("c-c", filter=focused)
        def close(event: KeyPressEvent) -> None:  # noqa: ARG001
            self.on_close()

        for keys, pages in (
            ((" ", "pagedown", "f", "c-f"), 1.0),
            (("b", "pageup", "c-b"), -1.0),
            (("d", "c-d"), 0.5),
            (("u", "c-u"), -0.5),
        ):
            for key in keys:
                bindings.add(key, filter=focused)(partial(self._scroll_page, pages=pages))

        @bindings.add("j", filter=focused)
        @bindings.add("down", filter=focused)
        @bindings.add("enter", filter=focused)
        def down(event: KeyPressEvent) -> None:
            self._scroll(event, 1)

        @bindings.add("k", filter=focused)
        @bindings.add("up", filter=focused)
        def up(event: KeyPressEvent) -> None:
            self._scroll(event, -1)

        @bindings.add("right", filter=focused)
        @bindings.add("l", filter=focused)
        def right(event: KeyPressEvent) -> None:
            self._scroll_horizontal(event, 1)

        @bindings.add("left", filter=focused)
        @bindings.add("h", filter=focused)
        def left(event: KeyPressEvent) -> None:
            self._scroll_horizontal(event, -1)

        @bindings.add("g", filter=focused)
        @bindings.add("home", filter=focused)
        def first(event: KeyPressEvent) -> None:
            event.current_buffer.cursor_position = 0

        @bindings.add("G", filter=focused)
        @bindings.add("end", filter=focused)
        def last(event: KeyPressEvent) -> None:
            event.current_buffer.cursor_position = len(event.current_buffer.text)

        @bindings.add("/", filter=focused)
        def find(event: KeyPressEvent) -> None:  # noqa: ARG001
            start_search(direction=SearchDirection.FORWARD)

        @bindings.add("?", filter=focused)
        def find_backwards(event: KeyPressEvent) -> None:  # noqa: ARG001
            start_search(direction=SearchDirection.BACKWARD)

        @bindings.add("n", filter=focused)
        def next_match(event: KeyPressEvent) -> None:
            event.current_buffer.apply_search(event.app.current_search_state, include_current_position=False)

        @bindings.add("N", filter=focused)
        def previous_match(event: KeyPressEvent) -> None:
            event.current_buffer.apply_search(~event.app.current_search_state, include_current_position=False)

        # Explicit search bindings also work when the main prompt uses Vi mode.
        bindings.add("enter", filter=is_searching)(search.accept_search)
        bindings.add("escape", filter=is_searching, eager=True)(search.abort_search)
        bindings.add("c-c", filter=is_searching)(search.abort_search)

    @staticmethod
    def _column_at_width(line: str, width: int) -> int:
        used = 0
        for column, char in enumerate(line):
            if used >= width:
                return column
            used += get_cwidth(char)
        return len(line)

    def _scroll_page(self, event: KeyPressEvent, *, pages: float) -> None:
        info = self.text.window.render_info
        if info is not None:
            amount = max(1, int(max(1, info.window_height - 1) * abs(pages)))
            self._scroll(event, amount if pages > 0 else -amount)

    def _scroll(self, event: KeyPressEvent, rows: int) -> None:
        """Move by display rows, including within lines taller than the viewport."""
        info = self.text.window.render_info
        if info is None or info.window_width == 0:
            return
        document = event.current_buffer.document
        line = document.cursor_position_row
        wrapped_row = 0 if self.chop else get_cwidth(document.current_line_before_cursor) // info.window_width
        target = wrapped_row + rows

        def height(number: int) -> int:
            return 1 if self.chop else info.get_height_for_line(number)

        while target < 0 and line > 0:
            line -= 1
            target += height(line)
        while target >= height(line) and line < document.line_count - 1:
            target -= height(line)
            line += 1
        target = max(0, min(target, height(line) - 1))
        # Chopped lines never wrap, so leave the cursor at the column the reader
        # scrolled to. Moving it to the start of the line would drag the view back
        # with it, since the window scrolls horizontally to keep the cursor visible.
        width = self.text.window.horizontal_scroll if self.chop else target * info.window_width
        column = self._column_at_width(document.lines[line], width)
        event.current_buffer.cursor_position = document.translate_row_col_to_index(line, column)
        self.text.window.vertical_scroll = line
        self.text.window.vertical_scroll_2 = target if height(line) > info.window_height else 0

    def _scroll_horizontal(self, event: KeyPressEvent, direction: int) -> None:
        info = self.text.window.render_info
        if info is None or not self.chop:
            return
        document = event.current_buffer.document
        target = max(0, self.text.window.horizontal_scroll + direction * max(1, info.window_width // 2))
        column = self._column_at_width(document.current_line, target)
        event.current_buffer.cursor_position = document.translate_row_col_to_index(document.cursor_position_row, column)
        self.text.window.horizontal_scroll = get_cwidth(document.current_line[:column])
