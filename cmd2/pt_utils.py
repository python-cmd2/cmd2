"""Utilities for integrating prompt_toolkit with cmd2."""

import re
from collections.abc import Callable, Iterable
from typing import (
    TYPE_CHECKING,
    Any,
)

from prompt_toolkit import (
    print_formatted_text,
)
from prompt_toolkit.completion import (
    Completer,
    Completion,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import History
from prompt_toolkit.lexers import Lexer
from rich.text import Text

from . import (
    constants,
    utils,
)
from . import rich_utils as ru
from .completion import CompletionItem
from .exceptions import CompletionError
from .styles import Cmd2Style

if TYPE_CHECKING:
    from .cmd2 import Cmd


BASE_DELIMITERS = " \t\n" + "".join(constants.QUOTES) + "".join(constants.REDIRECTION_CHARS)


class Cmd2Completer(Completer):
    """Completer that delegates to cmd2's completion logic."""

    def __init__(self, cmd_app: 'Cmd', custom_settings: utils.CustomCompletionSettings | None = None) -> None:
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

        try:
            completions = self.cmd_app.complete(
                text, line=line, begidx=begidx, endidx=endidx, custom_settings=self.custom_settings
            )
        except CompletionError as ex:
            # Don't print unless error has length
            err_str = str(ex)
            if err_str:
                general_console = ru.Cmd2GeneralConsole()
                with general_console.capture() as capture:
                    styled_err = Text(err_str, style=Cmd2Style.ERROR if ex.apply_style else "")
                    general_console.print(styled_err, end="")
                print_formatted_text(ANSI(capture.get()))
            return
        except Exception as ex:  # noqa: BLE001
            formatted_exception = self.cmd_app.format_exception(ex)
            print_formatted_text(ANSI(formatted_exception))
            return

        # Print formatted completions if present
        if completions.formatted_completions:
            print_formatted_text(ANSI("\n" + completions.formatted_completions))

        # Print hint if present and settings say we should
        if completions.completion_hint and (self.cmd_app.always_show_hint or not completions.matches):
            print_formatted_text(ANSI(completions.completion_hint))

        if not completions.matches:
            return

        # Now we iterate over completions.matches and completions.display_matches.
        # cmd2 separates completion matches (what is inserted) from display matches (what is shown).
        # prompt_toolkit Completion object takes 'text' (what is inserted) and 'display' (what is shown).

        # Check if we have display matches
        use_display_matches = bool(completions.display_matches)

        for i, match in enumerate(completions.matches):
            display = completions.display_matches[i] if use_display_matches else match
            display_meta: str | ANSI | None = None
            if isinstance(match, CompletionItem) and match.descriptive_data:
                if isinstance(match.descriptive_data[0], str):
                    display_meta = match.descriptive_data[0]
                elif isinstance(match.descriptive_data[0], Text):
                    # Convert rich renderable to prompt-toolkit formatted text
                    display_meta = ANSI(ru.rich_text_to_string(match.descriptive_data[0]))

            # Set offset to the start of the current word to overwrite it with the completion
            start_position = -len(text)
            yield Completion(match, start_position=start_position, display=display, display_meta=display_meta)


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

    def __init__(self, cmd_app: 'Cmd') -> None:
        """Initialize the lexer."""
        super().__init__()
        self.cmd_app = cmd_app

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
                    style = ''
                    if command in self.cmd_app.get_all_commands():
                        style = 'ansigreen'
                    elif command in self.cmd_app.aliases:
                        style = 'ansicyan'
                    elif command in self.cmd_app.macros:
                        style = 'ansimagenta'

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
                            tokens.append(('ansired', text))
                        elif (quoted or word) and text not in exclude_tokens:
                            tokens.append(('ansiyellow', text))
                        else:
                            tokens.append(('', text))
            elif line:
                # No command match found, add the entire line unstyled
                tokens.append(('', line))

            return tokens

        return get_line
