"""Utilities for integrating prompt_toolkit with cmd2."""

import re
from collections.abc import Callable, Iterable
from typing import (
    TYPE_CHECKING,
    Any,
)

from prompt_toolkit import print_formatted_text
from prompt_toolkit.completion import (
    Completer,
    Completion,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import History
from prompt_toolkit.lexers import Lexer

from . import (
    constants,
    utils,
)

if TYPE_CHECKING:
    from .cmd2 import Cmd


BASE_DELIMITERS = " \t\n" + "".join(constants.QUOTES) + "".join(constants.REDIRECTION_CHARS)


class Cmd2Completer(Completer):
    """Completer that delegates to cmd2's completion logic."""

    def __init__(
        self,
        cmd_app: 'Cmd',
        custom_settings: utils.CustomCompletionSettings | None = None,
    ) -> None:
        """Initialize prompt_toolkit based completer class."""
        self.cmd_app = cmd_app
        self.custom_settings = custom_settings

    def get_completions(self, document: Document, _complete_event: object) -> Iterable[Completion]:
        """Get completions for the current input."""
        # Find the beginning of the current word based on delimiters
        line = document.text
        cursor_pos = document.cursor_position

        # Define delimiters for completion to match cmd2/readline behavior
        delimiters = BASE_DELIMITERS
        if hasattr(self.cmd_app, 'statement_parser'):
            delimiters += "".join(self.cmd_app.statement_parser.terminators)

        # Find last delimiter before cursor to determine the word being completed
        begidx = 0
        for i in range(cursor_pos - 1, -1, -1):
            if line[i] in delimiters:
                begidx = i + 1
                break

        endidx = cursor_pos
        text = line[begidx:endidx]

        completions = self.cmd_app.complete(
            text, line=line, begidx=begidx, endidx=endidx, custom_settings=self.custom_settings
        )

        if completions.completion_error:
            print_formatted_text(ANSI(completions.completion_error))
            return

        # Print completion table if present
        if completions.completion_table:
            print_formatted_text(ANSI("\n" + completions.completion_table))

        # Print hint if present and settings say we should
        if completions.completion_hint and (self.cmd_app.always_show_hint or not completions):
            print_formatted_text(ANSI(completions.completion_hint))

        if not completions:
            return

        # The length of the user's input minus any shortcut.
        search_text_length = len(text) - completions._search_text_offset

        # If matches require quoting but the word isn't quoted yet, we insert the
        # opening quote directly into the buffer. We do this because if any completions
        # change text before the cursor (like prepending a quote), prompt-toolkit will
        # not return a common prefix to the command line. By modifying the buffer
        # and returning early, we trigger a new completion cycle where the quote
        # is already present, allowing for proper common prefix calculation.
        if completions._add_opening_quote and search_text_length > 0:
            buffer = self.cmd_app.session.app.current_buffer

            buffer.cursor_left(search_text_length)
            buffer.insert_text(completions._quote_char)
            buffer.cursor_right(search_text_length)
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

            # Finalize if there's only one match
            if len(completions) == 1 and completions.allow_finalization:
                # Close any open quote
                if completions._quote_char:
                    match_text += completions._quote_char

                # Add trailing space if the cursor is at the end of the line
                if endidx == len(line):
                    match_text += " "

            yield Completion(
                match_text,
                start_position=start_position,
                display=item.display,
                display_meta=item.display_meta,
            )


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


class Cmd2Lexer(Lexer):
    """Lexer that highlights cmd2 command names, aliases, and macros."""

    def __init__(
        self,
        cmd_app: 'Cmd',
        command_color: str = 'ansigreen',
        alias_color: str = 'ansicyan',
        macro_color: str = 'ansimagenta',
        flag_color: str = 'ansired',
        argument_color: str = 'ansiyellow',
    ) -> None:
        """Initialize the Lexer.

        :param cmd_app: cmd2.Cmd instance
        :param command_color: color to use for commands, defaults to 'ansigreen'
        :param alias_color: color to use for aliases, defaults to 'ansicyan'
        :param macro_color: color to use for macros, defaults to 'ansimagenta'
        :param flag_color: color to use for flags, defaults to 'ansired'
        :param argument_color: color to use for arguments, defaults to 'ansiyellow'
        """
        super().__init__()
        self.cmd_app = cmd_app
        self.command_color = command_color
        self.alias_color = alias_color
        self.macro_color = macro_color
        self.flag_color = flag_color
        self.argument_color = argument_color

    def lex_document(self, document: Document) -> Callable[[int], Any]:
        """Lex the document."""

        def get_line(lineno: int) -> list[tuple[str, str]]:
            """Return the tokens for the given line number."""
            line = document.lines[lineno]
            tokens: list[tuple[str, str]] = []

            # Use cmd2's command pattern to find the first word (the command)
            match = self.cmd_app.statement_parser._command_pattern.search(line)
            if match:
                # Group 1 is the command, Group 2 is the character(s) that terminated the command match
                command = match.group(1)
                cmd_start = match.start(1)
                cmd_end = match.end(1)

                # Add any leading whitespace
                if cmd_start > 0:
                    tokens.append(('', line[:cmd_start]))

                if command:
                    # Determine the style for the command
                    shortcut_found = False
                    for shortcut, _ in self.cmd_app.statement_parser.shortcuts:
                        if command.startswith(shortcut):
                            # Add the shortcut with the command style
                            tokens.append((self.command_color, shortcut))

                            # If there's more in the command word, it's an argument
                            if len(command) > len(shortcut):
                                tokens.append((self.argument_color, command[len(shortcut) :]))

                            shortcut_found = True
                            break

                    if not shortcut_found:
                        style = ''
                        if command in self.cmd_app.get_all_commands():
                            style = self.command_color
                        elif command in self.cmd_app.aliases:
                            style = self.alias_color
                        elif command in self.cmd_app.macros:
                            style = self.macro_color

                        # Add the command with the determined style
                        tokens.append((style, command))

                # Add the rest of the line
                if cmd_end < len(line):
                    rest = line[cmd_end:]
                    # Regex to match whitespace, flags, quoted strings, or other words
                    arg_pattern = re.compile(r'(\s+)|(--?[^\s\'"]+)|("[^"]*"?|\'[^\']*\'?)|([^\s\'"]+)')

                    # Get redirection tokens and terminators to avoid highlighting them as values
                    exclude_tokens = set(constants.REDIRECTION_TOKENS)
                    if hasattr(self.cmd_app, 'statement_parser'):
                        exclude_tokens.update(self.cmd_app.statement_parser.terminators)

                    for m in arg_pattern.finditer(rest):
                        space, flag, quoted, word = m.groups()
                        text = m.group(0)

                        if space:
                            tokens.append(('', text))
                        elif flag:
                            tokens.append((self.flag_color, text))
                        elif (quoted or word) and text not in exclude_tokens:
                            tokens.append((self.argument_color, text))
                        else:
                            tokens.append(('', text))
            elif line:
                # No command match found, add the entire line unstyled
                tokens.append(('', line))

            return tokens

        return get_line
