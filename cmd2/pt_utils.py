"""Utilities for integrating prompt_toolkit with cmd2."""

import re
from collections.abc import Iterable
from typing import (
    TYPE_CHECKING,
)

from prompt_toolkit import print_formatted_text
from prompt_toolkit.completion import (
    Completer,
    Completion,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import History

from . import (
    constants,
    utils,
)

if TYPE_CHECKING:
    from .cmd2 import Cmd


BASE_DELIMITERS = " \t\n" + "".join(constants.QUOTES) + "".join(constants.REDIRECTION_CHARS)


class Cmd2Completer(Completer):
    """Completer that delegates to cmd2's completion logic."""

    def __init__(self, cmd_app: 'Cmd', custom_settings: utils.CustomCompletionSettings | None = None) -> None:
        """Initialize prompt_toolkit based completer class."""
        self.cmd_app = cmd_app
        self.custom_settings = custom_settings

        # Define delimiters for completion to match cmd2/readline behavior
        delimiters = BASE_DELIMITERS
        if hasattr(self.cmd_app, 'statement_parser'):
            delimiters += "".join(self.cmd_app.statement_parser.terminators)

        # Regex pattern for a word: one or more characters that are NOT delimiters
        self.word_pattern = re.compile(f"[^{re.escape(delimiters)}]+")

    def get_completions(self, document: Document, _complete_event: object) -> Iterable[Completion]:
        """Get completions for the current input."""
        text = document.get_word_before_cursor(pattern=self.word_pattern)

        # We need the full line and indexes for cmd2
        line = document.text

        # Calculate begidx and endidx
        # get_word_before_cursor returns the word.
        # We need to find where this word starts.
        # document.cursor_position is the current cursor position.

        # text is the word before cursor.
        # So begidx should be cursor_position - len(text)
        # endidx should be cursor_position

        endidx = document.cursor_position
        begidx = endidx - len(text)

        # Call cmd2's complete method.
        # We pass state=0 to trigger the completion calculation.
        self.cmd_app.complete(text, 0, line=line, begidx=begidx, endidx=endidx, custom_settings=self.custom_settings)

        # Print formatted completions or hints above the prompt if present
        if self.cmd_app.formatted_completions:
            print_formatted_text(ANSI(self.cmd_app.formatted_completions.rstrip()))
        elif self.cmd_app.completion_hint:
            print_formatted_text(ANSI(self.cmd_app.completion_hint.rstrip()))

        # Now we iterate over self.cmd_app.completion_matches and self.cmd_app.display_matches
        matches = self.cmd_app.completion_matches
        display_matches = self.cmd_app.display_matches

        if not matches:
            return

        # cmd2 separates completion matches (what is inserted) from display matches (what is shown).
        # prompt_toolkit Completion object takes 'text' (what is inserted) and 'display' (what is shown).

        # Check if we have display matches and if they match the length of completion matches
        use_display_matches = len(display_matches) == len(matches)

        for i, match in enumerate(matches):
            display = display_matches[i] if use_display_matches else match

            # prompt_toolkit replaces the word before cursor by default if we use the default Completer?
            # No, we yield Completion(text, start_position=...).
            # Default start_position is 0 (append).

            start_position = -len(text)

            yield Completion(match, start_position=start_position, display=display)


class Cmd2History(History):
    """History that bridges cmd2's history storage with prompt_toolkit."""

    def __init__(self, cmd_app: 'Cmd') -> None:
        """Initialize prompt_toolkit based history wrapper class."""
        super().__init__()
        self.cmd_app = cmd_app

    def load_history_strings(self) -> Iterable[str]:
        """Yield strings from cmd2's history to prompt_toolkit."""
        for item in self.cmd_app.history:
            yield item.statement.raw

    def get_strings(self) -> list[str]:
        """Get the strings from the history."""
        # We override this to always get the latest history from cmd2
        # instead of caching it like the base class does.
        strings: list[str] = []
        last_item = None
        for item in self.cmd_app.history:
            if item.statement.raw != last_item:
                strings.append(item.statement.raw)
                last_item = item.statement.raw
        return strings

    def store_string(self, string: str) -> None:
        """prompt_toolkit calls this when a line is accepted.

        cmd2 handles history addition in its own loop (postcmd).
        We don't want to double add.
        However, PromptSession needs to know about it for the *current* session history navigation.
        If we don't store it here, UP arrow might not work for the just entered command
        unless cmd2 re-initializes the session or history object.

        This method is intentionally empty.
        """
