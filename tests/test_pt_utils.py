"""Unit tests for cmd2/pt_utils.py"""

from typing import cast
from unittest.mock import Mock

import pytest
from prompt_toolkit.document import Document

from cmd2 import pt_utils, utils
from cmd2.history import HistoryItem
from cmd2.parsing import Statement


# Mock for cmd2.Cmd
class MockCmd:
    def __init__(self):
        self.complete = Mock()
        self.completion_matches = []
        self.display_matches = []
        self.history = []


@pytest.fixture
def mock_cmd_app():
    return MockCmd()


class TestCmd2Completer:
    def test_get_completions_basic(self, mock_cmd_app):
        """Test basic completion without display matches."""
        completer = pt_utils.Cmd2Completer(cast(any, mock_cmd_app))

        # Setup document
        text = "foo"
        line = "command foo"
        cursor_position = len(line)
        document = Mock(spec=Document)
        document.get_word_before_cursor.return_value = text
        document.text = line
        document.cursor_position = cursor_position

        # Setup matches
        mock_cmd_app.completion_matches = ["foobar", "food"]
        mock_cmd_app.display_matches = []  # Empty means use completion matches for display

        # Call get_completions
        completions = list(completer.get_completions(document, None))

        # Verify cmd_app.complete was called correctly
        # begidx = cursor_position - len(text) = 11 - 3 = 8
        mock_cmd_app.complete.assert_called_once_with(text, 0, line=line, begidx=8, endidx=11, custom_settings=None)

        # Verify completions
        assert len(completions) == 2
        assert completions[0].text == "foobar"
        assert completions[0].start_position == -3
        # prompt_toolkit 3.0+ uses FormattedText for display
        assert completions[0].display == [('', 'foobar')]

        assert completions[1].text == "food"
        assert completions[1].start_position == -3
        assert completions[1].display == [('', 'food')]

    def test_get_completions_with_display_matches(self, mock_cmd_app):
        """Test completion with display matches."""
        completer = pt_utils.Cmd2Completer(cast(any, mock_cmd_app))

        # Setup document
        text = "f"
        line = "f"
        document = Mock(spec=Document)
        document.get_word_before_cursor.return_value = text
        document.text = line
        document.cursor_position = 1

        # Setup matches
        mock_cmd_app.completion_matches = ["foo", "bar"]
        mock_cmd_app.display_matches = ["Foo Display", "Bar Display"]

        # Call get_completions
        completions = list(completer.get_completions(document, None))

        # Verify completions
        assert len(completions) == 2
        assert completions[0].text == "foo"
        assert completions[0].display == [('', 'Foo Display')]

        assert completions[1].text == "bar"
        assert completions[1].display == [('', 'Bar Display')]

    def test_get_completions_mismatched_display_matches(self, mock_cmd_app):
        """Test completion when display_matches length doesn't match completion_matches."""
        completer = pt_utils.Cmd2Completer(cast(any, mock_cmd_app))

        document = Mock(spec=Document)
        document.get_word_before_cursor.return_value = ""
        document.text = ""
        document.cursor_position = 0

        mock_cmd_app.completion_matches = ["foo", "bar"]
        mock_cmd_app.display_matches = ["Foo Display"]  # Length mismatch

        completions = list(completer.get_completions(document, None))

        # Should ignore display_matches and use completion_matches for display
        assert len(completions) == 2
        assert completions[0].display == [('', 'foo')]
        assert completions[1].display == [('', 'bar')]

    def test_get_completions_empty(self, mock_cmd_app):
        """Test completion with no matches."""
        completer = pt_utils.Cmd2Completer(cast(any, mock_cmd_app))

        document = Mock(spec=Document)
        document.get_word_before_cursor.return_value = ""
        document.text = ""
        document.cursor_position = 0

        mock_cmd_app.completion_matches = []

        completions = list(completer.get_completions(document, None))

        assert len(completions) == 0

    def test_init_with_custom_settings(self, mock_cmd_app):
        """Test initializing with custom settings."""
        mock_parser = Mock()
        custom_settings = utils.CustomCompletionSettings(parser=mock_parser)
        completer = pt_utils.Cmd2Completer(cast(any, mock_cmd_app), custom_settings=custom_settings)

        document = Mock(spec=Document)
        document.get_word_before_cursor.return_value = ""
        document.text = ""
        document.cursor_position = 0

        mock_cmd_app.completion_matches = []

        list(completer.get_completions(document, None))

        mock_cmd_app.complete.assert_called_once()
        assert mock_cmd_app.complete.call_args[1]['custom_settings'] == custom_settings


class TestCmd2History:
    def make_history_item(self, text):
        statement = Mock(spec=Statement)
        statement.raw = text
        item = Mock(spec=HistoryItem)
        item.statement = statement
        return item

    def test_load_history_strings(self, mock_cmd_app):
        """Test loading history strings in reverse order with deduping."""
        history = pt_utils.Cmd2History(cast(any, mock_cmd_app))

        # Setup history items
        # History in cmd2 is oldest to newest
        items = [
            self.make_history_item("cmd1"),
            self.make_history_item("cmd2"),
            self.make_history_item("cmd2"),  # Duplicate
            self.make_history_item("cmd3"),
        ]
        mock_cmd_app.history = items

        # Expected: cmd3, cmd2, cmd1 (duplicates removed)
        result = list(history.load_history_strings())

        assert result == ["cmd3", "cmd2", "cmd1"]

    def test_load_history_strings_empty(self, mock_cmd_app):
        """Test loading history strings with empty history."""
        history = pt_utils.Cmd2History(cast(any, mock_cmd_app))

        mock_cmd_app.history = []

        result = list(history.load_history_strings())

        assert result == []

    def test_get_strings(self, mock_cmd_app):
        """Test get_strings uses lazy loading."""
        history = pt_utils.Cmd2History(cast(any, mock_cmd_app))

        items = [self.make_history_item("test")]
        mock_cmd_app.history = items

        # Initially not loaded
        assert not history._loaded

        strings = history.get_strings()

        assert strings == ["test"]
        assert history._loaded
        assert history._loaded_strings == ["test"]

        # Call again, should return cached strings
        # Modify underlying history to prove it uses cache
        mock_cmd_app.history = []
        strings2 = history.get_strings()
        assert strings2 == ["test"]

    def test_store_string(self, mock_cmd_app):
        """Test store_string does nothing."""
        history = pt_utils.Cmd2History(cast(any, mock_cmd_app))

        # Just ensure it doesn't raise error or modify cmd2 history
        history.store_string("new command")

        assert len(mock_cmd_app.history) == 0
