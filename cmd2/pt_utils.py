"""Utilities for integrating prompt_toolkit with cmd2."""

import asyncio
import dataclasses
import os
import re
import threading
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
from prompt_toolkit.buffer import (
    Buffer,
    CompletionState,
)
from prompt_toolkit.completion import (
    CompleteEvent,
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


# How long a completion which runs in a thread waits for the event loop before giving up on it
_EVENT_LOOP_TIMEOUT = 1.0


class _CompletionKeyEvent(CompleteEvent):
    """Requests the completion which cmd2's key binding for the default completion key starts.

    prompt-toolkit doesn't tell a completer what a request will do with its matches. This tells
    Cmd2Completer that the common prefix of the matches will be inserted, which is the one kind
    of request it can start again after inserting an opening quote.
    """

    def __init__(self) -> None:
        """Initialize the instance."""
        super().__init__(completion_requested=True)


class _QuoteInsertedEvent(CompleteEvent):
    """Requests the completion which Cmd2Completer starts after it has inserted an opening quote.

    It carries the matches which were found before the quote was inserted, so cmd2's completion
    logic doesn't run a second time. Since the matches travel with the request they were found for,
    no other request can be given them.
    """

    def __init__(self, document: Document, completions: "Completions") -> None:
        """Initialize the instance.

        :param document: the input, with the quote in it, which the matches are for
        :param completions: the matches, changed to what they are once the quote is present
        """
        super().__init__(completion_requested=True)
        self.document = document
        self.completions = completions


def _quote_is_closed(text_after_cursor: str, quote: str, *, opened_by_cmd2: bool, punctuation: str) -> bool:
    """Check whether the text after the cursor closes a quote which is open at the cursor.

    The same quote character further along the line is either the end of the argument being
    completed or part of something else: another quoted argument, or a word with an apostrophe
    or an inch mark in it. Which it is can't always be known, so this looks for a quote character
    in a place where only a closing quote would be.

    :param text_after_cursor: the rest of the line
    :param quote: the character which opened the quote
    :param opened_by_cmd2: True if cmd2 is adding the opening quote, False if the user typed it
    :param punctuation: the characters which end an unquoted word the way whitespace does,
                        which are the redirection characters and the terminators
    :return: True if the quote is already closed and a closing quote should not be added
    """
    # The word under the cursor ends with the quote character
    rest_of_word = re.split(rf"[\s{re.escape(punctuation)}]", text_after_cursor, maxsplit=1)[0]
    if rest_of_word.endswith(quote):
        return True

    # A quote which cmd2 adds goes around what was an unquoted word. An unquoted word ends at
    # whitespace or punctuation, so a quote character past it has nothing to do with this argument.
    if opened_by_cmd2:
        return False

    # An argument which the user quoted can have whitespace and punctuation in it. It is only
    # closed further along if no quote is left open when the line is read as continuing inside it.
    if _split_arguments(text_after_cursor, punctuation, open_quote=quote) is None:
        return False

    # Read the rest of the line as though the argument ended at the cursor
    arguments = _split_arguments(text_after_cursor, punctuation)
    if arguments is None:
        # It can't stand on its own, so it must be the rest of this argument
        return True

    # A quote character at the end of an unquoted word has no opening quote of its own. One in
    # the middle of a word is an apostrophe, and the quotes of a quoted argument belong to it.
    return any(argument[0] not in constants.QUOTES and argument.endswith(quote) for argument in arguments)


def _split_arguments(text: str, punctuation: str, open_quote: str = "") -> list[str] | None:
    """Split text into arguments the way the parser does, to see how its quote characters are used.

    A quote character only starts a quoted argument at the beginning of an argument, and a quoted
    argument ends at its closing quote. Anywhere else a quote character is an ordinary character.

    :param text: the text to split
    :param punctuation: the characters which end an unquoted word the way whitespace does
    :param open_quote: the quote character of a quoted argument which the text starts inside of
    :return: the arguments, where a quoted one keeps its quotes, or None if a quote is left open
    """
    arguments: list[str] = []
    argument = open_quote
    quote = open_quote

    for char in text:
        if quote:
            argument += char
            if char == quote:
                arguments.append(argument)
                argument = quote = ""
        elif char.isspace() or char in punctuation:
            if argument:
                arguments.append(argument)
                argument = ""
        elif not argument and char in constants.QUOTES:
            argument = quote = char
        else:
            argument += char

    if quote:
        return None

    if argument:
        arguments.append(argument)
    return arguments


def _completions_for_quoted_text(completions: "Completions") -> "Completions":
    """Change completions which need an opening quote into what they are once the quote is in the buffer.

    The quote goes after a shortcut, so the word being completed no longer includes the shortcut.
    """
    offset = completions._search_text_offset
    items = [dataclasses.replace(item, text=item.text[offset:]) for item in completions] if offset > 0 else completions.items
    return dataclasses.replace(
        completions,
        items=items,
        _add_opening_quote=False,
        _search_text_offset=0,
    )


def _in_event_loop(loop: asyncio.AbstractEventLoop | None) -> bool:
    """Return whether this is running in the event loop, as opposed to a thread which completes for it."""
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


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

    def _insert_quote_and_recomplete(self, document: Document, completions: "Completions", search_text_length: int) -> bool:
        """Arrange for an opening quote to be inserted and completion started again, once prompt-toolkit is ready.

        prompt-toolkit's async_completer is running the request this is called for. It discards the
        results of a request whose input changed while it ran, and it ignores a completion which is
        started before it has finished the request. So the buffer is left alone until the request has
        finished, and only if it finished without having been cancelled.

        :param document: the input being completed
        :param completions: the matches which need an opening quote
        :param search_text_length: how much of the text before the cursor the quote goes in front of
        :return: True if this has been arranged, in which case the request must return no completions.
                 False if there is no running event loop to do it.
        """
        app = get_app()
        loop = app.loop
        if loop is None or loop.is_closed():
            return False

        buffer = app.current_buffer
        quote_char = completions._quote_char

        # The matches for the document which has the quote in it, so the re-triggered cycle
        # doesn't invoke cmd2.complete() a second time.
        cached_completions = _completions_for_quoted_text(completions)

        # The request which async_completer is running, once that is known
        request_state: CompletionState | None = None

        # Whether async_completer has been seen to reach the end of the request with it still intact
        request_ended_intact = False

        def _recomplete() -> None:
            buffer.on_completions_changed -= _on_completions_changed

            # The user submitted or edited the line after the request finished
            if app.is_done or buffer.document != document:
                return

            # If the buffer completes while typing, inserting text starts a completion of its own.
            # prompt-toolkit would run that one and ignore the completion which is started below.
            buffer.cursor_left(search_text_length)
            buffer.insert_text(quote_char, fire_event=not buffer.complete_while_typing())
            buffer.cursor_right(search_text_length)

            # The matches go with the request for the re-triggered cycle. If prompt-toolkit
            # doesn't run that request, they are dropped along with it.
            complete_event = _QuoteInsertedEvent(buffer.document, cached_completions)
            buffer.start_completion(insert_common_part=True, complete_event=complete_event)

        def _on_completions_changed(_: Buffer) -> None:
            nonlocal request_ended_intact

            # The prompt has ended. Nobody is left to miss a notification, so the handler is removed here.
            if app.is_done:
                buffer.on_completions_changed -= _on_completions_changed
                return

            # When async_completer has all the results of a request, it notifies with the request's
            # state still in place. If there were no completions, it then clears the state and
            # notifies again. A request which was cancelled, or whose input was edited, had its state
            # cleared without a notification, so it is never seen intact here.
            if buffer.complete_state is request_state:
                request_ended_intact = True
                return

            if request_ended_intact and buffer.complete_state is None:
                # Run on the next loop tick, after _only_one_at_a_time resets its running flag
                loop.call_soon(_recomplete)
            else:
                # Removing the handler now would make prompt-toolkit skip the handler after it
                loop.call_soon(buffer.on_completions_changed.remove_handler, _on_completions_changed)

        def _wait_for_request_to_finish() -> None:
            nonlocal request_state

            # async_completer can't have finished the request yet, since it is waiting for
            # get_completions() to return. So if the state is already cleared, the request
            # was cancelled or the line was edited while cmd2 was completing.
            request_state = buffer.complete_state
            if request_state is not None:
                buffer.on_completions_changed += _on_completions_changed

        if _in_event_loop(loop):
            # async_completer is running get_completions() itself (e.g. complete_in_thread=False)
            _wait_for_request_to_finish()
        else:
            # get_completions() is running in a thread (e.g. complete_in_thread=True). Don't return
            # until the event loop is watching the request, or async_completer could finish it first.
            watching = threading.Event()

            def _wait_for_request_to_finish_in_event_loop() -> None:
                try:
                    _wait_for_request_to_finish()
                finally:
                    watching.set()

            loop.call_soon_threadsafe(_wait_for_request_to_finish_in_event_loop)
            watching.wait(timeout=_EVENT_LOOP_TIMEOUT)

        return True

    @staticmethod
    def _insert_quote_for_direct_request(document: Document, quote_char: str, search_text_length: int) -> Document | None:
        """Insert an opening quote into the buffer right away if a key binding is asking for completions itself.

        Some of prompt-toolkit's key bindings call get_completions() directly from the event loop, such
        as the one which lists completions like readline does. They read the buffer again once they
        have the completions, so the quote can go in before they are returned. Nothing which
        async_completer does is involved, since it isn't running a request.

        :param document: the input being completed
        :param quote_char: the quote to insert
        :param search_text_length: how much of the text before the cursor the quote goes in front of
        :return: the buffer's document with the quote in it, or None if this is not such a request
        """
        app = get_app()
        buffer = app.current_buffer
        if not _in_event_loop(app.loop) or buffer.complete_state is not None or buffer.document != document:
            return None

        buffer.cursor_left(search_text_length)
        buffer.insert_text(quote_char, fire_event=not buffer.complete_while_typing())
        buffer.cursor_right(search_text_length)
        return buffer.document

    def get_completions(self, document: Document, complete_event: object) -> Iterable[Completion]:
        """Get completions for the current input."""
        # Find the beginning of the current word based on delimiters
        line = document.text
        cursor_pos = document.cursor_position

        # Define delimiters for completion to match cmd2/readline behavior
        punctuation = "".join(constants.REDIRECTION_CHARS) + "".join(self._cmd_app.statement_parser.terminators)
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
        if isinstance(complete_event, _QuoteInsertedEvent) and complete_event.document == document:
            completions = complete_event.completions
        else:
            completions = self._cmd_app.complete(
                text, line=line, begidx=begidx, endidx=endidx, custom_settings=self.custom_settings
            )

        if completions.error:
            print_formatted_text(pt_filter_style(completions.error))
            return

        # The length of the user's input minus any shortcut.
        search_text_length = len(text) - completions._search_text_offset

        # If matches require quoting but the word isn't quoted yet, the opening quote goes in front
        # of text the user has typed. If any completions change text before the cursor (like
        # prepending a quote), prompt-toolkit will not return a common prefix to the command line.
        quote_inserted = False
        if completions and completions._add_opening_quote and search_text_length > 0:
            # For the completion key, whose request inserts that common prefix, the quote is
            # inserted into the buffer and completion is started again with the quote already present.
            if isinstance(complete_event, _CompletionKeyEvent) and self._insert_quote_and_recomplete(
                document, completions, search_text_length
            ):
                return

            # A key binding which asks for the completions itself gets the quote put in the
            # buffer first, and completions for the text as it is with the quote.
            quoted_document = self._insert_quote_for_direct_request(document, completions._quote_char, search_text_length)
            if quoted_document is not None:
                document = quoted_document
                line = document.text
                endidx = document.cursor_position

                # The quote went after any shortcut, so the word being completed starts after the quote
                text = text[completions._search_text_offset :]
                completions = _completions_for_quoted_text(completions)
                quote_inserted = True

            # Any other request gets the quote as part of each completion further down, so it
            # goes on to do what it was started for, such as selecting a match.

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

        # A completion only replaces text before the cursor, so text after it may already close
        # the quote. Adding another closing quote would then end the argument at the cursor and
        # leave the rest of it outside the quotes.
        closing_quote = completions._quote_char
        quote_opened_by_cmd2 = (
            quote_inserted or completions._add_opening_quote or isinstance(complete_event, _QuoteInsertedEvent)
        )
        if closing_quote and _quote_is_closed(
            line[endidx:], closing_quote, opened_by_cmd2=quote_opened_by_cmd2, punctuation=punctuation
        ):
            closing_quote = ""

        # Return the completions
        for item in completions:
            # Set offset to the start of the current word to overwrite it with the completion
            start_position = -len(text)
            match_text = item.text

            # If the matches need an opening quote which isn't in the buffer, then
            # prepend the quote here so it's included in the insertion.
            if completions._add_opening_quote:
                match_text = (
                    match_text[: completions._search_text_offset]
                    + completions._quote_char
                    + match_text[completions._search_text_offset :]
                )

            # A match which the user will keep completing, like a directory, is left as it is
            if completions.allow_finalization and item._allow_finalization:
                # Finalize if there's only one match
                if len(completions) == 1:
                    # Close any open quote
                    match_text += closing_quote

                    # Add trailing space if the cursor is at the end of the line
                    if endidx == len(line):
                        match_text += " "

                # A match chosen from several closes any open quote, so that accepting it does not
                # leave the quote open.
                elif closing_quote:
                    match_text += closing_quote

                    # With its quote closed the argument is finished, so add the trailing space too.
                    # Otherwise completing again would start a new argument right against the quote.
                    if endidx == len(line):
                        match_text += " "

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
