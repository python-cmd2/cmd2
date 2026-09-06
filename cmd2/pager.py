"""A pager view hosted by the main prompt-toolkit application."""

import threading
from collections.abc import Callable
from functools import partial

from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_focus, is_searching, to_filter
from prompt_toolkit.formatted_text import ANSI, fragment_list_to_text, to_formatted_text
from prompt_toolkit.formatted_text.base import StyleAndTextTuples
from prompt_toolkit.formatted_text.utils import split_lines
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


def _fragments(text: str) -> StyleAndTextTuples:
    """Parse captured output, dropping the trailing newline that ends its last line."""
    return to_formatted_text(ANSI(text.removesuffix("\n")))


def output_fits(text: str, columns: int, rows: int, *, chop: bool) -> bool:
    """Check rendered line heights, including wrapping and wide Unicode characters.

    Measuring the text itself keeps output that needs no scrolling from paying for a
    Pager's widgets and key bindings, which would only be built to be thrown away.
    """
    lines = fragment_list_to_text(_fragments(text)).split("\n")
    if chop:
        # Even one wide line needs a pager so its hidden columns remain
        # accessible through horizontal scrolling.
        return len(lines) <= rows and all(get_cwidth(line) <= columns for line in lines)
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
    """Preserve captured Rich styles while searching and scrolling plain text."""

    def __init__(self, fragments: StyleAndTextTuples) -> None:
        self.lines = list(split_lines(fragments))

    def lex_document(self, document: Document) -> Callable[[int], StyleAndTextTuples]:  # noqa: ARG002
        def get_line(number: int) -> StyleAndTextTuples:
            return self.lines[number] if number < len(self.lines) else []

        return get_line


class Pager:
    """Scrollable, searchable output; the host supplies the persistent toolbar."""

    def __init__(self, text: str, *, chop: bool) -> None:
        """Build an independent view without creating an application or input reader."""
        self.closed = threading.Event()
        self.on_close: Callable[[], None] = self.closed.set
        self.chop = chop
        fragments = _fragments(text)
        self.search = SearchToolbar()
        self.text = TextArea(
            text=fragment_list_to_text(fragments),
            lexer=_AnsiLexer(fragments),
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
