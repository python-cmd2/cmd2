"""Utilities for integrating prompt_toolkit with cmd2."""

import dataclasses
import os
import re
from collections.abc import (
    Callable,
    Iterable,
)
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
)

from prompt_toolkit import print_formatted_text
from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (
    Completer,
    Completion,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import History
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.output.color_depth import ColorDepth
from rich.style import Style, StyleType

from . import (
    constants,
    utils,
)
from . import rich_utils as ru
from . import string_utils as su
from .styles import Cmd2Style

if TYPE_CHECKING:  # pragma: no cover
    from rich.color import Color

    from .cmd2 import Cmd
    from .completion import Completions


BASE_DELIMITERS = " \t\n" + "".join(constants.QUOTES) + "".join(constants.REDIRECTION_CHARS)

# prompt_toolkit accepts these standard ANSI color names directly
ANSI_NAMES = (
    "ansiblack",
    "ansired",
    "ansigreen",
    "ansiyellow",
    "ansiblue",
    "ansimagenta",
    "ansicyan",
    "ansiwhite",
    "ansibrightblack",
    "ansibrightred",
    "ansibrightgreen",
    "ansibrightyellow",
    "ansibrightblue",
    "ansibrightmagenta",
    "ansibrightcyan",
    "ansibrightwhite",
)


def pt_filter_style(text: str | ANSI) -> str | ANSI:
    """Strip styles if disallowed by ru.ALLOW_STYLE. Otherwise return an ANSI object.

    This function is intended specifically for text rendered by prompt-toolkit.
    """
    # We only use prompt-toolkit to write to a terminal. Therefore
    # we only have to check if ALLOW_STYLE is Never.
    if ru.ALLOW_STYLE == ru.AllowStyle.NEVER:
        raw_text = text.value if isinstance(text, ANSI) else text
        return su.strip_style(raw_text)

    # String must be an ANSI object for prompt-toolkit to render ANSI style sequences.
    return text if isinstance(text, ANSI) else ANSI(text)


def pt_resolve_color_depth() -> ColorDepth:
    """Determine the prompt-toolkit ColorDepth based on NO_COLOR and ru.ALLOW_STYLE."""
    if os.environ.get("NO_COLOR") or ru.ALLOW_STYLE == ru.AllowStyle.NEVER:
        return ColorDepth.MONOCHROME
    return ColorDepth.TRUE_COLOR


@lru_cache(maxsize=256)
def rich_to_pt_color(color: "Color | None") -> str:
    """Convert a rich Color object to a prompt_toolkit color string."""
    if not color or color.is_default:
        return "default"

    # Use prompt_toolkit's 16 standard ansi color names if applicable.
    # This prevents overriding terminal themes with absolute RGB values.
    if color.number is not None and 0 <= color.number <= 15:
        return ANSI_NAMES[color.number]

    # For 8-bit and truecolor, we fallback to hex RGB strings which prompt-toolkit supports natively
    c = color.get_truecolor()
    return f"#{c.red:02x}{c.green:02x}{c.blue:02x}"


@lru_cache(maxsize=1024)
def rich_to_pt_style(rich_style: StyleType) -> str:
    """Convert a rich Style object to a prompt_toolkit style string."""
    if not rich_style:
        return ""

    if isinstance(rich_style, str):
        rich_style = Style.parse(rich_style)

    parts = []

    fg_color = rich_to_pt_color(rich_style.color)
    parts.append(f"fg:{fg_color}")

    bg_color = rich_to_pt_color(rich_style.bgcolor)
    parts.append(f"bg:{bg_color}")

    if rich_style.bold is not None:
        parts.append("bold" if rich_style.bold else "nobold")
    if rich_style.underline is not None:
        parts.append("underline" if rich_style.underline else "nounderline")
    if rich_style.strike is not None:
        parts.append("strike" if rich_style.strike else "nostrike")
    if rich_style.italic is not None:
        parts.append("italic" if rich_style.italic else "noitalic")
    if rich_style.blink is not None:
        parts.append("blink" if rich_style.blink else "noblink")
    if rich_style.reverse is not None:
        parts.append("reverse" if rich_style.reverse else "noreverse")
    if rich_style.conceal is not None:
        parts.append("hidden" if rich_style.conceal else "nohidden")
    if rich_style.dim is not None:
        parts.append("dim" if rich_style.dim else "nodim")
    return " ".join(parts)


class Cmd2Completer(Completer):
    """Completer that delegates to cmd2's completion logic."""

    def __init__(
        self,
        cmd_app: "Cmd",
        custom_settings: utils.CustomCompletionSettings | None = None,
    ) -> None:
        """Initialize prompt_toolkit based completer class."""
        self._cmd_app = cmd_app
        self.custom_settings = custom_settings
        self._pending_completions: tuple[Document, Completions] | None = None

    def get_completions(self, document: Document, complete_event: object) -> Iterable[Completion]:  # noqa: ARG002
        """Get completions for the current input."""
        # Find the beginning of the current word based on delimiters
        line = document.text
        cursor_pos = document.cursor_position

        # Define delimiters for completion to match cmd2/readline behavior
        delimiters = BASE_DELIMITERS
        delimiters += "".join(self._cmd_app.statement_parser.terminators)

        # Find last delimiter before cursor to determine the word being completed
        begidx = 0
        for i in range(cursor_pos - 1, -1, -1):
            if line[i] in delimiters:
                begidx = i + 1
                break

        endidx = cursor_pos
        text = line[begidx:endidx]

        # Reuse cached completions if this cycle was triggered right after inserting an opening quote
        pending = self._pending_completions
        self._pending_completions = None
        if pending is not None and pending[0] == document:
            completions = pending[1]
        else:
            completions = self._cmd_app.complete(
                text, line=line, begidx=begidx, endidx=endidx, custom_settings=self.custom_settings
            )

        if completions.error:
            print_formatted_text(pt_filter_style(completions.error))
            return

        # The length of the user's input minus any shortcut.
        search_text_length = len(text) - completions._search_text_offset

        # If matches require quoting but the word isn't quoted yet, we insert the
        # opening quote directly into the buffer. We do this because if any completions
        # change text before the cursor (like prepending a quote), prompt-toolkit will
        # not return a common prefix to the command line. By deferring the buffer edit
        # and restarting completion once the current cycle finishes, the quote is
        # already present on the next cycle without requiring a second Tab press.
        if completions and completions._add_opening_quote and search_text_length > 0:
            app = get_app()
            buffer = app.current_buffer
            quote_char = completions._quote_char

            def _insert_quote_and_recomplete() -> None:
                if buffer.document != document:
                    return

                buffer.cursor_left(search_text_length)
                buffer.insert_text(quote_char)
                buffer.cursor_right(search_text_length)
                buffer.start_completion(insert_common_part=True)

            def _schedule_recomplete() -> None:
                if buffer.complete_state is None:
                    # async_completer already finished (e.g. complete_in_thread=False)
                    _insert_quote_and_recomplete()
                else:
                    # async_completer is still finishing (e.g. complete_in_thread=True);
                    # wait until it clears complete_state, then run on the next loop tick
                    # after _only_one_at_a_time resets its running flag.
                    def _on_completions_changed(_: Buffer) -> None:
                        if buffer.complete_state is None:
                            buffer.on_completions_changed -= _on_completions_changed
                            if app.loop is not None and not app.loop.is_closed():
                                app.loop.call_soon(_insert_quote_and_recomplete)

                    buffer.on_completions_changed += _on_completions_changed

            if app.loop is not None and not app.loop.is_closed():
                # Cache completions for the post-quote document so the re-triggered cycle
                # doesn't invoke cmd2.complete() a second time.
                insert_pos = cursor_pos - search_text_length
                expected_doc = Document(
                    text=line[:insert_pos] + quote_char + line[insert_pos:],
                    cursor_position=cursor_pos + len(quote_char),
                )
                offset = completions._search_text_offset
                cached_items = (
                    [dataclasses.replace(item, text=item.text[offset:]) for item in completions]
                    if offset > 0
                    else completions.items
                )
                cached_completions = dataclasses.replace(
                    completions,
                    items=cached_items,
                    _add_opening_quote=False,
                    _search_text_offset=0,
                )
                self._pending_completions = (expected_doc, cached_completions)
                app.loop.call_soon_threadsafe(_schedule_recomplete)
            else:
                buffer.cursor_left(search_text_length)
                buffer.insert_text(quote_char)
                buffer.cursor_right(search_text_length)
            return

        # Print completion table if present
        if completions.table is not None:
            console = ru.Cmd2GeneralConsole(file=self._cmd_app.stdout)
            with console.capture() as capture:
                console.print(completions.table, end="", soft_wrap=False)
            print_formatted_text(pt_filter_style("\n" + capture.get()))

        if not completions:
            # Print hint if present
            if completions.hint:
                print_formatted_text(pt_filter_style(completions.hint))
            return

        # Return the completions
        for item in completions:
            # Set offset to the start of the current word to overwrite it with the completion
            start_position = -len(text)
            match_text = item.text

            # If we need a quote but didn't interrupt (because text was empty),
            # prepend the quote here so it's included in the insertion.
            if completions._add_opening_quote:
                match_text = (
                    match_text[: completions._search_text_offset]
                    + completions._quote_char
                    + match_text[completions._search_text_offset :]
                )

            if completions.allow_finalization:
                # Finalize if there's only one match
                if len(completions) == 1:
                    # Close any open quote
                    if completions._quote_char:
                        match_text += completions._quote_char

                    # Add trailing space if the cursor is at the end of the line
                    if endidx == len(line):
                        match_text += " "

                # A match chosen from several closes any open quote, so that accepting it does not
                # leave the quote open. A directory doesn't, since the user will keep completing it.
                elif completions._quote_char and item._allow_finalization:
                    match_text += completions._quote_char

            yield Completion(
                match_text,
                start_position=start_position,
                display=pt_filter_style(item.display),
                display_meta=pt_filter_style(item.display_meta),
            )


class Cmd2History(History):
    """A non-persistent, in-memory history buffer for prompt-toolkit.

    This class serves as the backing store for UI history navigation (e.g., arrowing
    through previous commands). It explicitly avoids handling persistence,
    deferring all permanent storage logic to the cmd2 application.
    """

    def __init__(self, history_strings: Iterable[str] | None = None) -> None:
        """Initialize the instance."""
        super().__init__()

        if history_strings:
            for string in history_strings:
                self.append_string(string)

        # Mark that self._loaded_strings is populated.
        self._loaded = True

    def append_string(self, string: str) -> None:
        """Override to filter our consecutive duplicates."""
        # History is sorted newest to oldest, so we compare to the first element.
        if string and (not self._loaded_strings or self._loaded_strings[0] != string):
            super().append_string(string)

    def store_string(self, string: str) -> None:
        """No-op: Persistent history data is stored in cmd2.Cmd.history."""

    def load_history_strings(self) -> Iterable[str]:
        """Yield strings from newest to oldest."""
        yield from self._loaded_strings

    def clear(self) -> None:
        """Clear the UI history navigation data."""
        self._loaded_strings.clear()


class Cmd2Lexer(Lexer):
    """Lexer that highlights cmd2 command names, aliases, and macros."""

    # Use the 'class:' prefix to look up styles in the prompt-toolkit theme
    COMMAND_STYLE = f"class:{Cmd2Style.LEXER_COMMAND}"
    ALIAS_STYLE = f"class:{Cmd2Style.LEXER_ALIAS}"
    MACRO_STYLE = f"class:{Cmd2Style.LEXER_MACRO}"
    FLAG_STYLE = f"class:{Cmd2Style.LEXER_FLAG}"
    ARGUMENT_STYLE = f"class:{Cmd2Style.LEXER_ARGUMENT}"

    def __init__(
        self,
        cmd_app: "Cmd",
    ) -> None:
        """Initialize the Lexer.

        :param cmd_app: cmd2.Cmd instance
        """
        super().__init__()
        self._cmd_app = cmd_app

    def lex_document(self, document: Document) -> Callable[[int], Any]:
        """Lex the document."""
        # Get redirection tokens and terminators to avoid highlighting them as values
        exclude_tokens = set(constants.REDIRECTION_TOKENS)
        exclude_tokens.update(self._cmd_app.statement_parser.terminators)
        arg_pattern = re.compile(r'(\s+)|(--?[^\s\'"]+)|("[^"]*"?|\'[^\']*\'?)|([^\s\'"]+)')

        def highlight_args(text: str, tokens: list[tuple[str, str]]) -> None:
            """Highlight arguments in a string."""
            for m in arg_pattern.finditer(text):
                space, flag, quoted, word = m.groups()
                match_text = m.group(0)

                if space:
                    tokens.append(("", match_text))
                elif flag:
                    tokens.append((self.FLAG_STYLE, match_text))
                elif (quoted or word) and match_text not in exclude_tokens:
                    tokens.append((self.ARGUMENT_STYLE, match_text))
                else:
                    tokens.append(("", match_text))

        def get_line(lineno: int) -> list[tuple[str, str]]:
            """Return the tokens for the given line number."""
            line = document.lines[lineno]
            tokens: list[tuple[str, str]] = []

            # No syntax highlighting if styles are disallowed
            if ru.ALLOW_STYLE == ru.AllowStyle.NEVER:
                tokens.append(("", line))
                return tokens

            # Only attempt to match a command on the first line
            if lineno == 0:
                # Use cmd2's command pattern to find the first word (the command)
                match = self._cmd_app.statement_parser._command_pattern.search(line)
                if match:
                    # Group 1 is the command, Group 2 is the character(s) that terminated the command match
                    command = match.group(1)
                    cmd_start = match.start(1)
                    cmd_end = match.end(1)

                    # Add any leading whitespace
                    if cmd_start > 0:
                        tokens.append(("", line[:cmd_start]))

                    if command:
                        # Determine the style for the command
                        shortcut_found = False
                        for shortcut, _ in self._cmd_app.statement_parser.shortcuts:
                            if command.startswith(shortcut):
                                # Add the shortcut with the command style
                                tokens.append((self.COMMAND_STYLE, shortcut))

                                # If there's more in the command word, it's an argument
                                if len(command) > len(shortcut):
                                    tokens.append((self.ARGUMENT_STYLE, command[len(shortcut) :]))

                                shortcut_found = True
                                break

                        if not shortcut_found:
                            style = ""
                            if command in self._cmd_app.get_all_commands():
                                style = self.COMMAND_STYLE
                            elif command in self._cmd_app.aliases:
                                style = self.ALIAS_STYLE
                            elif command in self._cmd_app.macros:
                                style = self.MACRO_STYLE

                            # Add the command with the determined style
                            tokens.append((style, command))

                    # Add the rest of the line as arguments
                    if cmd_end < len(line):
                        highlight_args(line[cmd_end:], tokens)
                else:
                    # No command match found on the first line
                    tokens.append(("", line))
            else:
                # All other lines are treated as arguments
                highlight_args(line, tokens)

            return tokens

        return get_line
