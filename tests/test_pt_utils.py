"""Unit tests for cmd2/pt_utils.py"""

import re
from typing import Any, cast
from unittest.mock import Mock

import pytest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document

import cmd2
from cmd2 import pt_utils, utils
from cmd2.history import HistoryItem
from cmd2.parsing import Statement


class MockSession:
    """Simulates a prompt_toolkit PromptSession."""

    def __init__(self):
        # Contains the CLI text and cursor position
        self.buffer = Buffer()

        # Mock the app structure: session -> app -> current_buffer
        self.app = Mock()
        self.app.current_buffer = self.buffer


# Mock for cmd2.Cmd
class MockCmd:
    def __init__(self):
        # Return empty completions by default
        self.complete = Mock(return_value=cmd2.Completions())

        self.always_show_hint = False
        self.history = []
        self.statement_parser = Mock()
        self.statement_parser.terminators = [';']
        self.statement_parser._command_pattern = re.compile(r'\A\s*(\S*?)(\s|\Z)')
        self.aliases = {}
        self.macros = {}
        self.all_commands = []
        self.session = MockSession()

    def get_all_commands(self):
        return self.all_commands


@pytest.fixture
def mock_cmd_app():
    return MockCmd()


class TestCmd2Lexer:
    def test_lex_document_command(self, mock_cmd_app):
        """Test lexing a command name."""
        mock_cmd_app.all_commands = ["help"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "help something"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('ansigreen', 'help'), ('', ' '), ('ansiyellow', 'something')]

    def test_lex_document_alias(self, mock_cmd_app):
        """Test lexing an alias."""
        mock_cmd_app.aliases = {"ls": "dir"}
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "ls -l"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('ansicyan', 'ls'), ('', ' '), ('ansired', '-l')]

    def test_lex_document_macro(self, mock_cmd_app):
        """Test lexing a macro."""
        mock_cmd_app.macros = {"my_macro": "some value"}
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "my_macro arg1"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('ansimagenta', 'my_macro'), ('', ' '), ('ansiyellow', 'arg1')]

    def test_lex_document_leading_whitespace(self, mock_cmd_app):
        """Test lexing with leading whitespace."""
        mock_cmd_app.all_commands = ["help"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "   help something"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('', '   '), ('ansigreen', 'help'), ('', ' '), ('ansiyellow', 'something')]

    def test_lex_document_unknown_command(self, mock_cmd_app):
        """Test lexing an unknown command."""
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "unknown command"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('', 'unknown'), ('', ' '), ('ansiyellow', 'command')]

    def test_lex_document_no_command(self, mock_cmd_app):
        """Test lexing an empty line or line with only whitespace."""
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "   "
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('', '   ')]

    def test_lex_document_arguments(self, mock_cmd_app):
        """Test lexing a command with flags and values."""
        mock_cmd_app.all_commands = ["help"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "help -v --name \"John Doe\" > out.txt"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            ('ansigreen', 'help'),
            ('', ' '),
            ('ansired', '-v'),
            ('', ' '),
            ('ansired', '--name'),
            ('', ' '),
            ('ansiyellow', '"John Doe"'),
            ('', ' '),
            ('', '>'),
            ('', ' '),
            ('ansiyellow', 'out.txt'),
        ]

    def test_lex_document_unclosed_quote(self, mock_cmd_app):
        """Test lexing with an unclosed quote."""
        mock_cmd_app.all_commands = ["echo"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "echo \"hello"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [('ansigreen', 'echo'), ('', ' '), ('ansiyellow', '"hello')]


class TestCmd2Completer:
    def test_get_completions(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test get_completions with matches."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # Set up document
        line = ""
        document = Document(line, cursor_position=0)

        # Set up matches
        completion_items = [
            cmd2.CompletionItem("foo", display="Foo Display"),
            cmd2.CompletionItem("bar", display="Bar Display"),
        ]
        cmd2_completions = cmd2.Completions(completion_items, completion_table="Table Data")
        mock_cmd_app.complete.return_value = cmd2_completions

        # Call get_completions
        completions = list(completer.get_completions(document, None))

        # Verify completions which are sorted by display field.
        assert len(completions) == len(cmd2_completions)
        assert completions[0].text == "bar"
        assert completions[0].display == [('', 'Bar Display')]

        assert completions[1].text == "foo"
        assert completions[1].display == [('', 'Foo Display')]

        # Verify that only the completion table printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert cmd2_completions.completion_table in str(args[0])

    def test_get_completions_no_matches(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test get_completions with no matches."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        document = Document("", cursor_position=0)

        # Set up matches
        cmd2_completions = cmd2.Completions(completion_hint="Completion Hint")
        mock_cmd_app.complete.return_value = cmd2_completions

        completions = list(completer.get_completions(document, None))
        assert not completions

        # Verify that only the completion hint printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert cmd2_completions.completion_hint in str(args[0])

    def test_get_completions_always_show_hints(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test that get_completions respects 'always_show_hint' and prints a hint even with no matches."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        document = Document("test", cursor_position=4)

        # Enable hint printing when there are no matches.
        mock_cmd_app.always_show_hint = True

        # Set up matches
        cmd2_completions = cmd2.Completions(completion_hint="Completion Hint")
        mock_cmd_app.complete.return_value = cmd2_completions

        completions = list(completer.get_completions(document, None))
        assert not completions

        # Verify that only the completion hint printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert cmd2_completions.completion_hint in str(args[0])

    def test_get_completions_with_error(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test get_completions with a completion_error."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        document = Document("", cursor_position=0)

        # Set up matches
        cmd2_completions = cmd2.Completions(completion_error="Completion Error")
        mock_cmd_app.complete.return_value = cmd2_completions

        completions = list(completer.get_completions(document, None))
        assert not completions

        # Verify that only the completion error printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert cmd2_completions.completion_error in str(args[0])

    @pytest.mark.parametrize(
        # search_text_offset is the starting index of the user-provided search text within a full match.
        # This accounts for leading shortcuts (e.g., in '@has', the offset is 1).
        ('line', 'match', 'search_text_offset'),
        [
            ('has', 'has space', 0),
            ('@has', '@has space', 1),
        ],
    )
    def test_get_completions_add_opening_quote_and_abort(self, line, match, search_text_offset, mock_cmd_app) -> None:
        """Test case where adding an opening quote changes text before cursor.

        This applies when there is search text.
        """
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # Set up document
        document = Document(line, cursor_position=len(line))

        # Set up matches
        completion_items = [cmd2.CompletionItem(match)]
        cmd2_completions = cmd2.Completions(
            completion_items,
            _add_opening_quote=True,
            _search_text_offset=search_text_offset,
            _quote_char='"',
        )
        mock_cmd_app.complete.return_value = cmd2_completions

        # Call get_completions
        completions = list(completer.get_completions(document, None))

        # get_completions inserted an opening quote in the buffer and then aborted before returning completions
        assert not completions

    @pytest.mark.parametrize(
        # search_text_offset is the starting index of the user-provided search text within a full match.
        # This accounts for leading shortcuts (e.g., in '@has', the offset is 1).
        ('line', 'matches', 'search_text_offset', 'quote_char', 'expected'),
        [
            # Single matches need opening quote, closing quote, and trailing space
            ('', ['has space'], 0, '"', ['"has space" ']),
            ('@', ['@has space'], 1, "'", ["@'has space' "]),
            # Multiple matches only need opening quote
            ('', ['has space', 'more space'], 0, '"', ['"has space', '"more space']),
            ('@', ['@has space', '@more space'], 1, "'", ["@'has space", "@'more space"]),
        ],
    )
    def test_get_completions_add_opening_quote_and_return_results(
        self, line, matches, search_text_offset, quote_char, expected, mock_cmd_app
    ) -> None:
        """Test case where adding an opening quote does not change text before cursor.

        This applies when search text is empty.
        """
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # Set up document
        document = Document(line, cursor_position=len(line))

        # Set up matches
        completion_items = [cmd2.CompletionItem(match) for match in matches]

        cmd2_completions = cmd2.Completions(
            completion_items,
            _add_opening_quote=True,
            _search_text_offset=search_text_offset,
            _quote_char=quote_char,
        )
        mock_cmd_app.complete.return_value = cmd2_completions

        # Call get_completions
        completions = list(completer.get_completions(document, None))

        # Compare results
        completion_texts = [c.text for c in completions]
        assert completion_texts == expected

    @pytest.mark.parametrize(
        ('line', 'match', 'quote_char', 'end_of_line', 'expected'),
        [
            # --- Unquoted search text ---
            # Append a trailing space when end_of_line is True
            ('ma', 'match', '', True, 'match '),
            ('ma', 'match', '', False, 'match'),
            # --- Quoted search text ---
            # Ensure closing quotes are added
            # Append a trailing space when end_of_line is True
            ('"ma', '"match', '"', True, '"match" '),
            ("'ma", "'match", "'", False, "'match'"),
        ],
    )
    def test_get_completions_allow_finalization(
        self, line, match, quote_char, end_of_line, expected, mock_cmd_app: MockCmd
    ) -> None:
        """Test that get_completions corectly handles finalizing single matches."""
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # Set up document
        cursor_position = len(line) if end_of_line else len(line) - 1
        document = Document(line, cursor_position=cursor_position)

        # Set up matches
        completion_items = [cmd2.CompletionItem(match)]
        cmd2_completions = cmd2.Completions(completion_items, _quote_char=quote_char)
        mock_cmd_app.complete.return_value = cmd2_completions

        # Call get_completions and compare results
        completions = list(completer.get_completions(document, None))
        assert completions[0].text == expected

    @pytest.mark.parametrize(
        ('line', 'match', 'quote_char', 'end_of_line', 'expected'),
        [
            # Do not add a trailing space or closing quote to any of the matches
            ('ma', 'match', '', True, 'match'),
            ('ma', 'match', '', False, 'match'),
            ('"ma', '"match', '"', True, '"match'),
            ("'ma", "'match", "'", False, "'match"),
        ],
    )
    def test_get_completions_do_not_allow_finalization(
        self, line, match, quote_char, end_of_line, expected, mock_cmd_app: MockCmd
    ) -> None:
        """Test that get_completions does not finalize single matches when allow_finalization if False."""
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # Set up document
        cursor_position = len(line) if end_of_line else len(line) - 1
        document = Document(line, cursor_position=cursor_position)

        # Set up matches
        completion_items = [cmd2.CompletionItem(match)]
        cmd2_completions = cmd2.Completions(
            completion_items,
            allow_finalization=False,
            _quote_char=quote_char,
        )
        mock_cmd_app.complete.return_value = cmd2_completions

        # Call get_completions and compare results
        completions = list(completer.get_completions(document, None))
        assert completions[0].text == expected

    def test_init_with_custom_settings(self, mock_cmd_app: MockCmd) -> None:
        """Test initializing with custom settings."""
        mock_parser = Mock()
        custom_settings = utils.CustomCompletionSettings(parser=mock_parser)
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app), custom_settings=custom_settings)

        document = Document("", cursor_position=0)

        mock_cmd_app.complete.return_value = cmd2.Completions()

        list(completer.get_completions(document, None))

        mock_cmd_app.complete.assert_called_once()
        assert mock_cmd_app.complete.call_args[1]['custom_settings'] == custom_settings

    def test_get_completions_no_statement_parser(self, mock_cmd_app: MockCmd) -> None:
        """Test initialization and completion without statement_parser."""
        del mock_cmd_app.statement_parser
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        document = Document("foo bar", cursor_position=7)
        list(completer.get_completions(document, None))

        # Should still work with default delimiters
        mock_cmd_app.complete.assert_called_once()

    def test_get_completions_custom_delimiters(self, mock_cmd_app: MockCmd) -> None:
        """Test that custom delimiters (terminators) are respected."""
        mock_cmd_app.statement_parser.terminators = ['#']
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # '#' should act as a word boundary
        document = Document("cmd#arg", cursor_position=7)
        list(completer.get_completions(document, None))

        # text should be "arg", begidx=4, endidx=7
        mock_cmd_app.complete.assert_called_with("arg", line="cmd#arg", begidx=4, endidx=7, custom_settings=None)


class TestCmd2History:
    def make_history_item(self, text):
        statement = Mock(spec=Statement)
        statement.raw = text
        item = Mock(spec=HistoryItem)
        item.statement = statement
        return item

    def test_load_history_strings(self, mock_cmd_app):
        """Test loading history strings yields all items in forward order."""
        history = pt_utils.Cmd2History(cast(Any, mock_cmd_app))

        # Set up history items
        # History in cmd2 is oldest to newest
        items = [
            self.make_history_item("cmd1"),
            self.make_history_item("cmd2"),
            self.make_history_item("cmd2"),  # Duplicate
            self.make_history_item("cmd3"),
        ]
        mock_cmd_app.history = items

        # Expected: cmd1, cmd2, cmd2, cmd3 (raw iteration)
        result = list(history.load_history_strings())

        assert result == ["cmd1", "cmd2", "cmd2", "cmd3"]

    def test_load_history_strings_empty(self, mock_cmd_app):
        """Test loading history strings with empty history."""
        history = pt_utils.Cmd2History(cast(Any, mock_cmd_app))

        mock_cmd_app.history = []

        result = list(history.load_history_strings())

        assert result == []

    def test_get_strings(self, mock_cmd_app):
        """Test get_strings returns deduped strings and does not cache."""
        history = pt_utils.Cmd2History(cast(Any, mock_cmd_app))

        items = [
            self.make_history_item("cmd1"),
            self.make_history_item("cmd2"),
            self.make_history_item("cmd2"),  # Duplicate
            self.make_history_item("cmd3"),
        ]
        mock_cmd_app.history = items

        # Expect deduped: cmd1, cmd2, cmd3
        strings = history.get_strings()
        assert strings == ["cmd1", "cmd2", "cmd3"]

        # Modify underlying history to prove it does NOT use cache
        mock_cmd_app.history.append(self.make_history_item("cmd4"))
        strings2 = history.get_strings()
        assert strings2 == ["cmd1", "cmd2", "cmd3", "cmd4"]

    def test_store_string(self, mock_cmd_app):
        """Test store_string does nothing."""
        history = pt_utils.Cmd2History(cast(Any, mock_cmd_app))

        # Just ensure it doesn't raise error or modify cmd2 history
        history.store_string("new command")

        assert len(mock_cmd_app.history) == 0
