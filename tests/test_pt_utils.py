"""Unit tests for cmd2/pt_utils.py"""

import asyncio
import io
import re
import threading
from collections.abc import Iterable
from typing import Any, cast
from unittest.mock import Mock

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import CompleteEvent, Completer, Completion, ThreadedCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import (
    ANSI,
    to_formatted_text,
)
from prompt_toolkit.input.defaults import DummyInput
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.output.color_depth import ColorDepth
from prompt_toolkit.output.defaults import DummyOutput
from prompt_toolkit.shortcuts import CompleteStyle
from rich.table import Table

import cmd2
from cmd2 import (
    Cmd2Style,
    pt_utils,
    stylize,
    utils,
)
from cmd2 import rich_utils as ru
from cmd2 import string_utils as su
from cmd2.pt_utils import (
    Cmd2Lexer,
    pt_filter_style,
    pt_resolve_color_depth,
)

from .conftest import with_ansi_style


# Mock for cmd2.Cmd
class MockCmd:
    def __init__(self) -> None:
        # Return empty completions by default
        self.complete = Mock(return_value=cmd2.Completions())

        self.stdout = io.StringIO()
        self.statement_parser = Mock()
        self.statement_parser.terminators = [";"]
        self.statement_parser.shortcuts = []
        self.statement_parser._command_pattern = re.compile(r"\A\s*(\S*?)(\s|\Z)")
        self.aliases = {}
        self.macros = {}
        self.all_commands = []
        self.active_session = Mock()
        self.active_session.complete_style = CompleteStyle.MULTI_COLUMN

    def get_all_commands(self) -> list[str]:
        return self.all_commands


@pytest.fixture
def mock_cmd_app() -> MockCmd:
    return MockCmd()


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_pt_filter_style_always() -> None:
    """This should preserve all styles and return ANSI."""
    unstyled = "unstyled"
    result = pt_filter_style(unstyled)
    assert isinstance(result, ANSI)
    assert result.value == unstyled

    styled = stylize("styled", Cmd2Style.COMMAND_LINE)
    result = pt_filter_style(styled)
    assert isinstance(result, ANSI)
    assert result.value == styled


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_pt_filter_style_terminal() -> None:
    """This should preserve all styles and return ANSI."""
    unstyled = "unstyled"
    result = pt_filter_style(unstyled)
    assert isinstance(result, ANSI)
    assert result.value == unstyled

    styled = stylize("styled", Cmd2Style.COMMAND_LINE)
    result = pt_filter_style(styled)
    assert isinstance(result, ANSI)
    assert result.value == styled


@with_ansi_style(ru.AllowStyle.NEVER)
def test_pt_filter_style_never() -> None:
    """This should strip all styles and return str."""
    unstyled = "unstyled"
    result = pt_filter_style(unstyled)
    assert isinstance(result, str)
    assert result == unstyled

    styled = stylize("styled", Cmd2Style.COMMAND_LINE)
    result = pt_filter_style(styled)
    assert isinstance(result, str)
    assert result == su.strip_style(styled)


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_pt_resolve_color_depth_always(monkeypatch) -> None:
    # Clear NO_COLOR to ensure colors are not suppressed
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert pt_resolve_color_depth() == ColorDepth.TRUE_COLOR


@with_ansi_style(ru.AllowStyle.TERMINAL)
def test_pt_resolve_color_depth_terminal(monkeypatch) -> None:
    # Mock NO_COLOR to an empty string to ensure colors are not suppressed
    monkeypatch.setenv("NO_COLOR", "")
    assert pt_resolve_color_depth() == ColorDepth.TRUE_COLOR


@with_ansi_style(ru.AllowStyle.NEVER)
def test_pt_resolve_color_depth_never(monkeypatch) -> None:
    # Under NEVER, colors are suppressed regardless of NO_COLOR
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert pt_resolve_color_depth() == ColorDepth.MONOCHROME


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_pt_resolve_color_depth_no_color(monkeypatch) -> None:
    # Mock NO_COLOR to ensure colors are suppressed
    monkeypatch.setenv("NO_COLOR", "1")
    assert pt_resolve_color_depth() == ColorDepth.MONOCHROME


class TestCmd2Lexer:
    @with_ansi_style(ru.AllowStyle.NEVER)
    def test_lex_document_no_style(self, mock_cmd_app):
        """Test lexing when styles are disallowed."""
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "help something"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [("", line)]

    def test_lex_document_command(self, mock_cmd_app):
        """Test lexing a command name."""
        mock_cmd_app.all_commands = ["help"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "help something"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            (Cmd2Lexer.COMMAND_STYLE, "help"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, "something"),
        ]

    def test_lex_document_alias(self, mock_cmd_app):
        """Test lexing an alias."""
        mock_cmd_app.aliases = {"ls": "dir"}
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "ls -l"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            (Cmd2Lexer.ALIAS_STYLE, "ls"),
            ("", " "),
            (Cmd2Lexer.FLAG_STYLE, "-l"),
        ]

    def test_lex_document_macro(self, mock_cmd_app):
        """Test lexing a macro."""
        mock_cmd_app.macros = {"my_macro": "some value"}
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "my_macro arg1"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            (Cmd2Lexer.MACRO_STYLE, "my_macro"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, "arg1"),
        ]

    def test_lex_document_leading_whitespace(self, mock_cmd_app):
        """Test lexing with leading whitespace."""
        mock_cmd_app.all_commands = ["help"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "   help something"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            ("", "   "),
            (Cmd2Lexer.COMMAND_STYLE, "help"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, "something"),
        ]

    def test_lex_document_unknown_command(self, mock_cmd_app):
        """Test lexing an unknown command."""
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "unknown command"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            ("", "unknown"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, "command"),
        ]

    def test_lex_document_no_command(self, mock_cmd_app):
        """Test lexing an empty line or line with only whitespace."""
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "   "
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [("", "   ")]

    def test_lex_document_no_match(self, mock_cmd_app):
        """Test lexing when command pattern fails to match."""
        # Force the pattern to not match anything
        mock_cmd_app.statement_parser._command_pattern = re.compile(r"something_impossible")
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = "test command"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [("", line)]

    def test_lex_document_arguments(self, mock_cmd_app):
        """Test lexing a command with flags and values."""
        mock_cmd_app.all_commands = ["help"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = 'help -v --name "John Doe" > out.txt'
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            (Cmd2Lexer.COMMAND_STYLE, "help"),
            ("", " "),
            (Cmd2Lexer.FLAG_STYLE, "-v"),
            ("", " "),
            (Cmd2Lexer.FLAG_STYLE, "--name"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, '"John Doe"'),
            ("", " "),
            ("", ">"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, "out.txt"),
        ]

    def test_lex_document_unclosed_quote(self, mock_cmd_app):
        """Test lexing with an unclosed quote."""
        mock_cmd_app.all_commands = ["echo"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        line = 'echo "hello'
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)

        assert tokens == [
            (Cmd2Lexer.COMMAND_STYLE, "echo"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, '"hello'),
        ]

    def test_lex_document_shortcut(self, mock_cmd_app):
        """Test lexing a shortcut."""
        mock_cmd_app.statement_parser.shortcuts = [("!", "shell")]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        # Case 1: Shortcut glued to argument
        line = "!ls"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)
        assert tokens == [
            (Cmd2Lexer.COMMAND_STYLE, "!"),
            (Cmd2Lexer.ARGUMENT_STYLE, "ls"),
        ]

        line = "! ls"
        document = Document(line)
        get_line = lexer.lex_document(document)
        tokens = get_line(0)
        assert tokens == [
            (Cmd2Lexer.COMMAND_STYLE, "!"),
            ("", " "),
            (Cmd2Lexer.ARGUMENT_STYLE, "ls"),
        ]

    def test_lex_document_multiline(self, mock_cmd_app):
        """Test lexing a multiline command."""
        mock_cmd_app.all_commands = ["orate"]
        lexer = pt_utils.Cmd2Lexer(cast(Any, mock_cmd_app))

        # Command on first line, argument on second line that looks like a command
        line = "orate\nhelp"
        document = Document(line)
        get_line = lexer.lex_document(document)

        # First line should have command
        tokens0 = get_line(0)
        assert tokens0 == [(Cmd2Lexer.COMMAND_STYLE, "orate")]

        # Second line should have argument (not command)
        tokens1 = get_line(1)
        assert tokens1 == [(Cmd2Lexer.ARGUMENT_STYLE, "help")]


class TestCmd2Completer:
    def test_get_completions(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test get_completions with matches."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # Set up document
        line = ""
        document = Document(line, cursor_position=0)

        # Test plain and styled values for display and display_meta
        foo_text = "foo"
        foo_display = "Foo Display"
        foo_meta = "Foo Meta"

        bar_text = "bar"
        bar_display = stylize("Bar Display", Cmd2Style.SUCCESS)
        bar_meta = stylize("Bar Meta", Cmd2Style.WARNING)

        # Set up matches
        completion_items = [
            cmd2.CompletionItem(foo_text, display=foo_display, display_meta=foo_meta),
            cmd2.CompletionItem(bar_text, display=bar_display, display_meta=bar_meta),
        ]

        table = Table("Table Header")
        table.add_row("Table Data")
        cmd2_completions = cmd2.Completions(completion_items, table=table)
        mock_cmd_app.complete.return_value = cmd2_completions

        # Call get_completions
        completions = list(completer.get_completions(document, None))

        assert len(completions) == len(cmd2_completions)

        assert completions[0].text == bar_text
        assert to_formatted_text(completions[0].display) == to_formatted_text(ANSI(bar_display))
        assert to_formatted_text(completions[0].display_meta) == to_formatted_text(ANSI(bar_meta))

        assert completions[1].text == foo_text
        assert to_formatted_text(completions[1].display) == to_formatted_text(ANSI(foo_display))
        assert to_formatted_text(completions[1].display_meta) == to_formatted_text(ANSI(foo_meta))

        # Verify that only the completion table printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert "Table Header" in str(args[0])
        assert "Table Data" in str(args[0])

    def test_get_completions_no_matches(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test get_completions with no matches."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        document = Document("", cursor_position=0)

        # Set up matches
        cmd2_completions = cmd2.Completions(hint="Completion Hint")
        mock_cmd_app.complete.return_value = cmd2_completions

        completions = list(completer.get_completions(document, None))
        assert not completions

        # Verify that only the completion hint printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert cmd2_completions.hint in str(args[0])

    def test_get_completions_with_error(self, mock_cmd_app: MockCmd, monkeypatch) -> None:
        """Test get_completions with a completion error."""
        mock_print = Mock()
        monkeypatch.setattr(pt_utils, "print_formatted_text", mock_print)

        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        document = Document("", cursor_position=0)

        # Set up matches
        cmd2_completions = cmd2.Completions(error="Completion Error")
        mock_cmd_app.complete.return_value = cmd2_completions

        completions = list(completer.get_completions(document, None))
        assert not completions

        # Verify that only the completion error printed
        assert mock_print.call_count == 1
        args, _ = mock_print.call_args
        assert cmd2_completions.error in str(args[0])

    @pytest.mark.parametrize(
        # search_text_offset is the starting index of the user-provided search text within a full match.
        # This accounts for leading shortcuts (e.g., in '@has', the offset is 1).
        ("line", "match", "search_text_offset", "expected"),
        [
            ("has", "has space", 0, '"has space" '),
            ("@has", "@has space", 1, '@"has space" '),
        ],
    )
    @pytest.mark.parametrize(
        "complete_event",
        [
            None,
            CompleteEvent(completion_requested=True),
            # Not even the completion key's request can be started again without a running application
            pt_utils._CompletionKeyEvent(),
        ],
        ids=["no-event", "requested", "completion-key"],
    )
    def test_get_completions_add_opening_quote_in_front_of_search_text(
        self, line, match, search_text_offset, expected, complete_event, mock_cmd_app
    ) -> None:
        """Test that a match carries the opening quote when it goes in front of text which was already typed."""
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
        completions = list(completer.get_completions(document, complete_event))

        # The completion replaces everything which was typed
        assert [(c.text, c.start_position) for c in completions] == [(expected, -len(line))]

    @pytest.mark.parametrize(
        ("complete_style", "buffer_line", "requested_line", "cursor_position", "expected_matches", "expected_buffer_line"),
        [
            # The quote is put in the buffer, where the readline-style binding reads the line from again,
            # so the match doesn't have to change text which is in front of the cursor
            (CompleteStyle.READLINE_LIKE, "edit has", "edit has", 8, ['has space" '], 'edit "has'),
            # The quote was added by cmd2, so a quote character in a later word doesn't close it
            (CompleteStyle.READLINE_LIKE, 'edit has 5" nail', 'edit has 5" nail', 8, ['has space"'], 'edit "has 5" nail'),
            # The request is not for what the buffer holds, so the buffer is left alone
            (CompleteStyle.READLINE_LIKE, "edit other", "edit has", 8, ['"has space" '], "edit other"),
            # Other bindings which ask directly, like Meta-* in Emacs mode, insert what they are given.
            # They get whole matches with their own quotes and the buffer is left alone.
            (CompleteStyle.MULTI_COLUMN, "edit has", "edit has", 8, ['"has space" '], "edit has"),
            (CompleteStyle.COLUMN, "edit has", "edit has", 8, ['"has space" '], "edit has"),
        ],
    )
    def test_get_completions_add_opening_quote_for_synchronous_request(
        self,
        complete_style,
        buffer_line,
        requested_line,
        cursor_position,
        expected_matches,
        expected_buffer_line,
        mock_cmd_app: MockCmd,
    ) -> None:
        """Verify what a request made directly by one of prompt-toolkit's key bindings gets."""
        mock_cmd_app.active_session.complete_style = complete_style

        def complete(*_args: Any, **_kwargs: Any) -> cmd2.Completions:
            # cmd2 switches the session to one of its menu styles whenever it completes
            mock_cmd_app.active_session.complete_style = CompleteStyle.COLUMN
            return cmd2.Completions([cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"')

        mock_cmd_app.complete.side_effect = complete
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        async def run_test() -> tuple[list[str], str]:
            buf = Buffer(document=Document(buffer_line, cursor_position=cursor_position), completer=completer)
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            with set_app(app):
                # This is how display_completions_like_readline() and the Emacs Meta-* binding ask for completions
                complete_event = CompleteEvent(completion_requested=True)
                document = Document(requested_line, cursor_position=cursor_position)
                completions = list(completer.get_completions(document, complete_event))
                await self._wait_for_completion(app)
            return [c.text for c in completions], buf.text

        assert asyncio.run(run_test()) == (expected_matches, expected_buffer_line)

    @pytest.mark.parametrize("complete_in_thread", [False, True])
    @pytest.mark.parametrize(
        ("line", "matches", "search_text_offset", "expected_text", "expected_completion_count"),
        [
            # Multiple matches: inserts opening quote + common prefix and displays completions
            ("edit has", ["has space 1", "has space 2"], 0, 'edit "has space ', 2),
            # Single match: inserts opening quote + match + closing quote + trailing space, no lingering menu
            ("edit has", ["has space"], 0, 'edit "has space" ', 0),
            # Shortcut prefix: inserts opening quote after shortcut and completes
            ("@has", ["@has space"], 1, '@"has space" ', 0),
        ],
    )
    def test_get_completions_add_opening_quote_retriggers_completion(
        self,
        complete_in_thread: bool,
        line: str,
        matches: list[str],
        search_text_offset: int,
        expected_text: str,
        expected_completion_count: int,
        mock_cmd_app: MockCmd,
        mocker: Any,
    ) -> None:
        """Verify inserting an opening quote restarts completion using cached results without re-calling complete()."""
        table = Table()
        table.add_column("Match")
        table.add_row("info")

        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem(m) for m in matches],
            table=table,
            _add_opening_quote=True,
            _search_text_offset=search_text_offset,
            _quote_char='"',
        )
        mock_print = mocker.patch("cmd2.pt_utils.print_formatted_text")

        base_completer: Completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        completer: Completer = ThreadedCompleter(base_completer) if complete_in_thread else base_completer

        async def run_completion() -> tuple[str, int]:
            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=completer)
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                # Wait for all completion background tasks (first + re-triggered) to finish
                for _ in range(20):
                    tasks = list(app._background_tasks)
                    if tasks:
                        await asyncio.gather(*tasks)
                    await asyncio.sleep(0)
                    if not app._background_tasks and buf.text != line:
                        break

            count = len(buf.complete_state.completions) if buf.complete_state else 0
            return buf.text, count

        final_text, completion_count = asyncio.run(run_completion())
        assert final_text == expected_text
        assert completion_count == expected_completion_count
        # Cached completions were reused on the re-triggered cycle: complete() and table print each ran once
        assert mock_cmd_app.complete.call_count == 1
        assert mock_print.call_count == 1

    @staticmethod
    async def _wait_for_completion(app: Application[None]) -> None:
        """Wait for a completion, and any completion which it restarts, to finish."""
        for _ in range(10):
            tasks = list(app._background_tasks)
            if tasks:
                await asyncio.gather(*tasks)
            await asyncio.sleep(0.005)

    @pytest.mark.parametrize(
        ("interruption", "expected_text", "expected_calls"),
        [
            ("cancel", "edit has", 2),
            # prompt-toolkit completes the edited line itself, which is one more call
            ("edit", "edit hasx", 3),
        ],
    )
    def test_get_completions_add_opening_quote_abandoned_request(
        self, interruption: str, expected_text: str, expected_calls: int, mock_cmd_app: MockCmd
    ) -> None:
        """Verify nothing is inserted or kept for a request which is cancelled or outdated while cmd2 is completing."""
        line = "edit has"
        completer = ThreadedCompleter(pt_utils.Cmd2Completer(cast(Any, mock_cmd_app)))

        async def run_test() -> tuple[str, str]:
            loop = asyncio.get_running_loop()
            completing = asyncio.Event()
            interrupted = threading.Event()

            def slow_complete(text: str, *_args: Any, **_kwargs: Any) -> cmd2.Completions:
                # Keep the request busy in its thread until it has been interrupted
                loop.call_soon_threadsafe(completing.set)
                interrupted.wait(timeout=5)
                if text != "has":
                    return cmd2.Completions()
                return cmd2.Completions([cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"')

            mock_cmd_app.complete.side_effect = slow_complete

            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=completer)
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = loop

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await completing.wait()
                if interruption == "cancel":
                    buf.cancel_completion()
                else:
                    buf.insert_text("x")
                interrupted.set()
                await self._wait_for_completion(app)
                text_after_interruption = buf.text

                # The next request for the original line has to ask cmd2 again
                buf.set_document(Document(line, cursor_position=len(line)))
                mock_cmd_app.complete.side_effect = None
                mock_cmd_app.complete.return_value = cmd2.Completions(
                    [cmd2.CompletionItem("has changed")], _add_opening_quote=True, _quote_char='"'
                )
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
                return text_after_interruption, buf.text

        text_after_interruption, final_text = asyncio.run(run_test())
        assert text_after_interruption == expected_text
        assert final_text == 'edit "has changed" '
        assert mock_cmd_app.complete.call_count == expected_calls

    @pytest.mark.parametrize("complete_in_thread", [False, True])
    def test_get_completions_add_opening_quote_with_complete_while_typing(
        self, complete_in_thread: bool, mock_cmd_app: MockCmd
    ) -> None:
        """Verify inserting the quote doesn't start an automatic completion which takes the place of the restart."""
        line = "edit has"

        def complete(_text: str, *, line: str, **_kwargs: Any) -> cmd2.Completions:
            if '"' in line:
                return cmd2.Completions([cmd2.CompletionItem("has space")], _quote_char='"')
            return cmd2.Completions([cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"')

        mock_cmd_app.complete.side_effect = complete
        base_completer: Completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        completer: Completer = ThreadedCompleter(base_completer) if complete_in_thread else base_completer

        async def run_test() -> str:
            buf = Buffer(
                document=Document(line, cursor_position=len(line)),
                completer=completer,
                complete_while_typing=True,
            )
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
            return buf.text

        assert asyncio.run(run_test()) == 'edit "has space" '

        # The line with only the quote inserted was completed from the matches which had already been found.
        # prompt-toolkit then completes the finished line itself, as it does after any text is inserted.
        completed_lines = [call.kwargs["line"] for call in mock_cmd_app.complete.call_args_list]
        assert completed_lines == [line, 'edit "has space" ']

    @pytest.mark.parametrize("complete_while_typing", [False, True])
    def test_get_completions_add_opening_quote_updates_suggestion(
        self, complete_while_typing: bool, mock_cmd_app: MockCmd
    ) -> None:
        """Verify the line with the quote in it is offered to auto-suggest, as any other inserted text is."""
        line = "edit has"
        mock_cmd_app.complete.return_value = cmd2.Completions(
            # These have nothing in common past what was typed, so the quote is all which gets inserted
            [cmd2.CompletionItem("has space"), cmd2.CompletionItem("hash")],
            _add_opening_quote=True,
            _quote_char='"',
        )
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        suggested_for: list[str] = []

        class RecordsRequests(AutoSuggest):
            def get_suggestion(self, _buffer: Buffer, document: Document) -> Suggestion | None:
                suggested_for.append(document.text)
                return None

        async def run_test() -> str:
            buf = Buffer(
                document=Document(line, cursor_position=len(line)),
                completer=completer,
                auto_suggest=RecordsRequests(),
                complete_while_typing=complete_while_typing,
            )
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
            return buf.text

        assert asyncio.run(run_test()) == 'edit "has'
        assert suggested_for == ['edit "has']

        # Inserting the quote didn't make the buffer complete the line on its own
        assert mock_cmd_app.complete.call_count == 1

    def test_get_completions_add_opening_quote_waits_for_running_request(self, mock_cmd_app: MockCmd) -> None:
        """Verify the quote is inserted once prompt-toolkit has finished a request it was still waiting on.

        This is what happens when a completion which runs in a thread takes a while. prompt-toolkit
        ignores a completion which is started before it has finished the request.
        """
        line = "edit has"
        completer = ThreadedCompleter(pt_utils.Cmd2Completer(cast(Any, mock_cmd_app)))

        async def run_test() -> str:
            loop = asyncio.get_running_loop()
            completing = asyncio.Event()
            waited_on = threading.Event()

            def slow_complete(*_args: Any, **_kwargs: Any) -> cmd2.Completions:
                # Don't return until prompt-toolkit is waiting for the results
                loop.call_soon_threadsafe(completing.set)
                waited_on.wait(timeout=5)
                return cmd2.Completions([cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"')

            mock_cmd_app.complete.side_effect = slow_complete

            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=completer)
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = loop

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await completing.wait()
                waited_on.set()
                await self._wait_for_completion(app)

            # cmd2 has stopped listening to the buffer
            handlers = buf.on_completions_changed._handlers
            assert [handler.__qualname__ for handler in handlers if "Cmd2Completer" in handler.__qualname__] == []
            return buf.text

        assert asyncio.run(run_test()) == 'edit "has space" '
        assert mock_cmd_app.complete.call_count == 1

    def test_get_completions_add_opening_quote_cancelled_before_request_finished(self, mock_cmd_app: MockCmd) -> None:
        """Verify nothing is inserted if the request is cancelled after cmd2 has completed it.

        prompt-toolkit hasn't been told that the request is finished at that point.
        """
        line = "edit has"
        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"'
        )
        cmd2_completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        async def run_test() -> str:
            loop = asyncio.get_running_loop()
            cancelled = False

            class CancelledAfterCompleting(Completer):
                """Has the user cancel the first request right after cmd2 has returned its results."""

                def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
                    nonlocal cancelled
                    yield from cmd2_completer.get_completions(document, complete_event)
                    if not cancelled:
                        cancelled = True
                        loop.call_soon_threadsafe(buf.cancel_completion)

            buf = Buffer(
                document=Document(line, cursor_position=len(line)),
                completer=ThreadedCompleter(CancelledAfterCompleting()),
            )
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = loop

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
            return buf.text

        assert asyncio.run(run_test()) == line
        assert mock_cmd_app.complete.call_count == 1

    @pytest.mark.parametrize("complete_in_thread", [False, True])
    def test_get_completions_add_opening_quote_keeps_selection_of_other_requests(
        self, complete_in_thread: bool, mock_cmd_app: MockCmd
    ) -> None:
        """Verify a request which selects a match gets the quote in each match instead of a restarted completion.

        Starting again would turn it into a request for the common prefix of the matches. That is
        only right for a request which comes from the completion key.
        """
        line = "edit has"
        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem("has space 1"), cmd2.CompletionItem("has space 2")],
            _add_opening_quote=True,
            _quote_char='"',
        )
        base_completer: Completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        completer: Completer = ThreadedCompleter(base_completer) if complete_in_thread else base_completer

        async def run_test() -> tuple[str, int | None]:
            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=completer)
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            with set_app(app):
                # What Ctrl-P does in Vi insert mode
                buf.start_completion(select_last=True)
                await self._wait_for_completion(app)
            assert buf.complete_state is not None
            return buf.text, buf.complete_state.complete_index

        assert asyncio.run(run_test()) == ('edit "has space 2" ', 1)
        assert mock_cmd_app.complete.call_count == 1

    def test_get_completions_add_opening_quote_does_not_hide_notifications(self, mock_cmd_app: MockCmd) -> None:
        """Verify a listener registered after cmd2's own still hears that the first request finished."""
        line = "edit has"
        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"'
        )
        cmd2_completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        async def run_test() -> list[tuple[str, bool]]:
            heard: list[tuple[str, bool]] = []
            listening = False

            def listener(buffer: Buffer) -> None:
                heard.append((buffer.text, buffer.complete_state is None))

            class RegistersListener(Completer):
                """Adds a listener once cmd2 has registered its own for the first request."""

                def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
                    nonlocal listening
                    yield from cmd2_completer.get_completions(document, complete_event)
                    if not listening:
                        listening = True
                        buf.on_completions_changed += listener

            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=RegistersListener())
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
            assert buf.text == 'edit "has space" '
            return heard

        # prompt-toolkit clears the state of the first request and says so before the quote is inserted
        assert (line, True) in asyncio.run(run_test())

    def test_get_completions_add_opening_quote_skips_if_prompt_ended(self, mock_cmd_app: MockCmd) -> None:
        """Verify the quote is not inserted if the line is submitted just as the request finishes."""
        line = "edit has"
        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem("has space")], _add_opening_quote=True, _quote_char='"'
        )
        cmd2_completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        async def run_test() -> str:
            loop = asyncio.get_running_loop()
            listening = False

            def end_prompt_when_request_finishes(buffer: Buffer) -> None:
                # prompt-toolkit clears the state once the request has returned no matches. cmd2 has been told
                # that already, since it listens ahead of this, and is about to insert the quote.
                if buffer.complete_state is None and app.future is None:
                    app.future = loop.create_future()
                    app.future.set_result(None)

            class RegistersListener(Completer):
                """Adds a listener once cmd2 has registered its own for the first request."""

                def get_completions(self, document: Document, complete_event: CompleteEvent) -> Iterable[Completion]:
                    nonlocal listening
                    yield from cmd2_completer.get_completions(document, complete_event)
                    if not listening:
                        listening = True
                        buf.on_completions_changed += end_prompt_when_request_finishes

            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=RegistersListener())
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = loop

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
            return buf.text

        assert asyncio.run(run_test()) == line

    def test_get_completions_add_opening_quote_skips_if_document_changed(self, mock_cmd_app: MockCmd) -> None:
        """Verify deferred quote insertion bails out if the user edits the buffer just as the request finishes."""
        line = "edit has"
        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem("has space")],
            _add_opening_quote=True,
            _search_text_offset=0,
            _quote_char='"',
        )
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        async def run_test() -> str:
            buf = Buffer(document=Document(line, cursor_position=len(line)), completer=completer)
            app: Application[None] = Application(
                layout=Layout(Window(BufferControl(buffer=buf))),
                input=DummyInput(),
                output=DummyOutput(),
            )
            app.loop = asyncio.get_running_loop()

            def edit_when_request_finishes(_: Buffer) -> None:
                # prompt-toolkit clears the completion state once the request has returned no matches.
                # The quote has not been inserted yet at that point.
                if buf.complete_state is None and buf.text == line:
                    buf.insert_text("x")

            buf.on_completions_changed += edit_when_request_finishes

            with set_app(app):
                buf.start_completion(insert_common_part=True, complete_event=pt_utils._CompletionKeyEvent())
                await self._wait_for_completion(app)
            return buf.text

        assert asyncio.run(run_test()) == "edit hasx"
        assert mock_cmd_app.complete.call_count == 1

    @pytest.mark.parametrize(
        # search_text_offset is the starting index of the user-provided search text within a full match.
        # This accounts for leading shortcuts (e.g., in '@has', the offset is 1).
        ("line", "matches", "search_text_offset", "quote_char", "expected"),
        [
            # Single matches need opening quote, closing quote, and trailing space
            ("", ["has space"], 0, '"', ['"has space" ']),
            ("@", ["@has space"], 1, "'", ["@'has space' "]),
            # Multiple matches need the same, so choosing one of them leaves it finished
            ("", ["has space", "more space"], 0, '"', ['"has space" ', '"more space" ']),
            ("@", ["@has space", "@more space"], 1, "'", ["@'has space' ", "@'more space' "]),
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
        ("line", "match", "quote_char", "end_of_line", "expected"),
        [
            # --- Unquoted search text ---
            # Append a trailing space when end_of_line is True
            ("ma", "match", "", True, "match "),
            ("ma", "match", "", False, "match"),
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
        """Test that get_completions correctly handles finalizing single matches."""
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
        ("line", "match", "quote_char", "end_of_line", "expected"),
        [
            # Do not add a trailing space or closing quote to any of the matches
            ("ma", "match", "", True, "match"),
            ("ma", "match", "", False, "match"),
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

    @pytest.mark.parametrize(
        ("line", "items", "quote_char", "allow_finalization", "expected"),
        [
            # Each match closes a quote which is open and adds a trailing space
            (
                '"ma',
                [cmd2.CompletionItem("match one"), cmd2.CompletionItem("match two")],
                '"',
                True,
                ['match one" ', 'match two" '],
            ),
            (
                "'ma",
                [cmd2.CompletionItem("match one"), cmd2.CompletionItem("match two")],
                "'",
                True,
                ["match one' ", "match two' "],
            ),
            # Nothing is added when no quote is open
            ("ma", [cmd2.CompletionItem("match"), cmd2.CompletionItem("matter")], "", True, ["match", "matter"]),
            # No match closes the quote when the matches are not allowed to be finalized
            (
                '"ma',
                [cmd2.CompletionItem("match one"), cmd2.CompletionItem("match two")],
                '"',
                False,
                ["match one", "match two"],
            ),
            # A match which can't be finalized itself, like a directory, leaves the quote open
            (
                '"ma',
                [cmd2.CompletionItem("match dir/", _allow_finalization=False), cmd2.CompletionItem("match file")],
                '"',
                True,
                ["match dir/", 'match file" '],
            ),
        ],
    )
    def test_get_completions_close_quote_of_each_of_several_matches(
        self, line, items, quote_char, allow_finalization, expected, mock_cmd_app: MockCmd
    ) -> None:
        """Test that a match chosen from several does not leave its quote open."""
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        document = Document(line, cursor_position=len(line))

        mock_cmd_app.complete.return_value = cmd2.Completions(
            items,
            allow_finalization=allow_finalization,
            _quote_char=quote_char,
        )

        completions = list(completer.get_completions(document, None))
        assert [c.text for c in completions] == expected

    @pytest.mark.parametrize(
        ("line", "matches", "quote_char", "expected"),
        [
            # A closing quote right after the cursor is never doubled
            ('"ma"', ["match"], '"', ["match"]),
            ('"ma"', ["match one", "match two"], '"', ["match one", "match two"]),
            ("'ma' more", ["match one", "match two"], "'", ["match one", "match two"]),
            # Otherwise the only match closes its quote
            ('"ma.txt"', ["match"], '"', ['match"']),
            ('"ma more', ["match"], '"', ['match"']),
            ("\"ma'", ["match"], '"', ['match"']),
            ('"ma --title="x"', ["match"], '"', ['match"']),
            # A match chosen from several leaves a quote which the user typed as it is
            ('"ma.txt"', ["match one", "match two"], '"', ["match one", "match two"]),
            ('"ma more', ["match one", "match two"], '"', ["match one", "match two"]),
            ('"ma "next"', ["match one", "match two"], '"', ["match one", "match two"]),
        ],
    )
    def test_get_completions_closing_quote_in_the_middle_of_a_line(
        self, line, matches, quote_char, expected, mock_cmd_app: MockCmd
    ) -> None:
        """Test what is added to a match when the user typed the opening quote and text follows the cursor."""
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # The cursor is right after the search text
        document = Document(line, cursor_position=3)

        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem(match) for match in matches],
            _quote_char=quote_char,
        )

        completions = list(completer.get_completions(document, None))
        assert [c.text for c in completions] == expected

    @pytest.mark.parametrize(
        ("line", "cursor_position", "matches", "expected"),
        [
            # The word which cmd2 puts in quotes ended at the cursor, so each match closes the quote
            ("ma more", 2, ["match one", "match two"], ['"match one"', '"match two"']),
            ("ma 'a\"b'", 2, ["match one", "match two"], ['"match one"', '"match two"']),
            ("ma 'a\"b'", 2, ["match"], ['"match"']),
            # The word carries on after the cursor, so what follows may be the rest of it
            ('ma"', 2, ["match one", "match two"], ['"match one', '"match two']),
            ("mab", 2, ["match one", "match two"], ['"match one', '"match two']),
            ('ma"', 2, ["match"], ['"match']),
            ("mab", 2, ["match"], ['"match"']),
        ],
    )
    @pytest.mark.parametrize("quote_already_inserted", [False, True])
    def test_get_completions_close_quote_which_cmd2_opened(
        self, line, cursor_position, matches, expected, quote_already_inserted, mock_cmd_app: MockCmd
    ) -> None:
        """Test what is added to a match when cmd2 adds the opening quote and text follows the cursor."""
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        items = [cmd2.CompletionItem(match) for match in matches]

        if quote_already_inserted:
            # The quote was put in the buffer and completion was started again with the matches found before
            document = Document('"' + line, cursor_position=cursor_position + 1)
            complete_event: object = pt_utils._QuoteInsertedEvent(document, cmd2.Completions(items, _quote_char='"'))
            expected = [text.removeprefix('"') for text in expected]
        else:
            # The quote is part of each match
            document = Document(line, cursor_position=cursor_position)
            complete_event = None
            mock_cmd_app.complete.return_value = cmd2.Completions(items, _add_opening_quote=True, _quote_char='"')

        completions = list(completer.get_completions(document, complete_event))
        assert [c.text for c in completions] == expected

    @pytest.mark.parametrize(
        ("line", "quote_char", "expected"),
        [
            ("ma", "", "match dir/"),
            ('"ma', '"', "match dir/"),
        ],
    )
    def test_get_completions_single_match_which_is_not_finished(
        self, line, quote_char, expected, mock_cmd_app: MockCmd
    ) -> None:
        """Test that the only match is left open when it is marked as one the user will keep completing.

        This is what a completer gets if it filters the results of path_complete() or
        delimiter_complete() down to a single directory-like match.
        """
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        document = Document(line, cursor_position=len(line))

        mock_cmd_app.complete.return_value = cmd2.Completions(
            [cmd2.CompletionItem("match dir/", _allow_finalization=False)],
            _quote_char=quote_char,
        )

        completions = list(completer.get_completions(document, None))
        assert [c.text for c in completions] == [expected]

    def test_get_completions_ignores_matches_found_for_another_document(self, mock_cmd_app: MockCmd) -> None:
        """Verify matches which were found before a quote was inserted are only used for the line they are for."""
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))
        quoted_document = Document('edit "has', cursor_position=9)
        found = cmd2.Completions([cmd2.CompletionItem("has space")], _quote_char='"')
        complete_event = pt_utils._QuoteInsertedEvent(quoted_document, found)

        # They are used for the line which the quote was inserted in
        completions = list(completer.get_completions(quoted_document, complete_event))
        assert [c.text for c in completions] == ['has space" ']
        assert mock_cmd_app.complete.call_count == 0

        # The user typed another character before the completion started
        mock_cmd_app.complete.return_value = cmd2.Completions([cmd2.CompletionItem("hash value")], _quote_char='"')
        edited_document = Document('edit "hash', cursor_position=10)
        completions = list(completer.get_completions(edited_document, complete_event))
        assert [c.text for c in completions] == ['hash value" ']
        assert mock_cmd_app.complete.call_count == 1

    def test_init_with_custom_settings(self, mock_cmd_app: MockCmd) -> None:
        """Test initializing with custom settings."""
        mock_parser = Mock()
        custom_settings = utils.CustomCompletionSettings(parser=mock_parser)
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app), custom_settings=custom_settings)

        document = Document("", cursor_position=0)

        mock_cmd_app.complete.return_value = cmd2.Completions()

        list(completer.get_completions(document, None))

        mock_cmd_app.complete.assert_called_once()
        assert mock_cmd_app.complete.call_args[1]["custom_settings"] == custom_settings

    def test_get_completions_custom_delimiters(self, mock_cmd_app: MockCmd) -> None:
        """Test that custom delimiters (terminators) are respected."""
        mock_cmd_app.statement_parser.terminators = ["#"]
        completer = pt_utils.Cmd2Completer(cast(Any, mock_cmd_app))

        # '#' should act as a word boundary
        document = Document("cmd#arg", cursor_position=7)
        list(completer.get_completions(document, None))

        # text should be "arg", begidx=4, endidx=7
        mock_cmd_app.complete.assert_called_with("arg", line="cmd#arg", begidx=4, endidx=7, custom_settings=None)


class TestCmd2History:
    def test_load_history_strings(self):
        """Test loading history strings yields all items newest to oldest."""

        history_strings = ["cmd1", "cmd2", "cmd2", "cmd3", "cmd2"]
        history = pt_utils.Cmd2History(history_strings)
        assert history._loaded

        # Consecutive duplicates are removed
        expected = ["cmd2", "cmd3", "cmd2", "cmd1"]
        assert list(history.load_history_strings()) == expected

    def test_load_history_strings_empty(self):
        """Test loading history strings with empty history."""
        history = pt_utils.Cmd2History()
        assert history._loaded
        assert list(history.load_history_strings()) == []

        history = pt_utils.Cmd2History([])
        assert history._loaded
        assert list(history.load_history_strings()) == []

        history = pt_utils.Cmd2History(None)
        assert history._loaded
        assert list(history.load_history_strings()) == []

    def test_get_strings(self):
        history_strings = ["cmd1", "cmd2", "cmd2", "cmd3", "cmd2"]
        history = pt_utils.Cmd2History(history_strings)
        assert history._loaded

        # Consecutive duplicates are removed
        expected = ["cmd1", "cmd2", "cmd3", "cmd2"]
        assert history.get_strings() == expected

    def test_append_string(self):
        """Test that append_string() adds data."""
        history = pt_utils.Cmd2History()
        assert history._loaded
        assert not history._loaded_strings

        history.append_string("new command")
        assert len(history._loaded_strings) == 1
        assert history._loaded_strings[0] == "new command"

        # Show that consecutive duplicates are filtered
        history.append_string("new command")
        assert len(history._loaded_strings) == 1
        assert history._loaded_strings[0] == "new command"

        # Show that new items are placed at the front
        history.append_string("even newer command")
        assert len(history._loaded_strings) == 2
        assert history._loaded_strings[0] == "even newer command"
        assert history._loaded_strings[1] == "new command"

    def test_store_string(self):
        """Test that store_string() does nothing."""
        history = pt_utils.Cmd2History()
        assert history._loaded
        assert not history._loaded_strings

        history.store_string("new command")
        assert not history._loaded_strings

    def test_clear(self):
        history_strings = ["cmd1", "cmd2"]
        history = pt_utils.Cmd2History(history_strings)
        assert history._loaded
        assert history.get_strings() == history_strings

        history.clear()
        assert not history.get_strings()


class TestRichToPtColor:
    def test_rich_to_pt_color_none(self):
        assert pt_utils.rich_to_pt_color(None) == "default"

    def test_rich_to_pt_color_default(self):
        from rich.color import Color

        c = Color.parse("default")
        assert pt_utils.rich_to_pt_color(c) == "default"

    def test_rich_to_pt_color_standard(self):
        from rich.color import Color

        c = Color.parse("red")
        assert pt_utils.rich_to_pt_color(c) == "ansired"
        c = Color.parse("bright_red")
        assert pt_utils.rich_to_pt_color(c) == "ansibrightred"
        # Test a standard color initialized by number
        c = Color.from_ansi(2)
        assert pt_utils.rich_to_pt_color(c) == "ansigreen"

    def test_rich_to_pt_color_eight_bit(self):
        from rich.color import Color

        # 155 is an 8-bit color
        c = Color.from_ansi(155)
        # Should convert to truecolor hex equivalent #afff5f
        assert pt_utils.rich_to_pt_color(c) == "#afff5f"

    def test_rich_to_pt_color_truecolor(self):
        from rich.color import Color

        c = Color.parse("#123456")
        assert pt_utils.rich_to_pt_color(c) == "#123456"


class TestRichToPtStyle:
    def test_rich_to_pt_style_none(self):
        assert pt_utils.rich_to_pt_style(None) == ""

    def test_rich_to_pt_style_string(self):
        pt_style = pt_utils.rich_to_pt_style("bold red on blue")
        assert "fg:ansired" in pt_style
        assert "bg:ansiblue" in pt_style
        assert "bold" in pt_style
        assert "nobold" not in pt_style

    def test_rich_to_pt_style_color(self):
        from rich.style import Style

        style = Style(color="#123456")
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "fg:#123456" in pt_style
        assert "bg:default" in pt_style

    def test_rich_to_pt_style_bgcolor(self):
        from rich.style import Style

        style = Style(bgcolor="#654321")
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "fg:default" in pt_style
        assert "bg:#654321" in pt_style

    def test_rich_to_pt_style_default_color(self):
        from rich.style import Style

        style = Style(color="default", bgcolor="default")
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "fg:default" in pt_style
        assert "bg:default" in pt_style

    def test_rich_to_pt_style_bold(self):
        from rich.style import Style

        style = Style(bold=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "bold" in pt_style
        assert "nobold" not in pt_style

    def test_rich_to_pt_style_nobold(self):
        from rich.style import Style

        style = Style(bold=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "nobold" in pt_style

    def test_rich_to_pt_style_underline(self):
        from rich.style import Style

        style = Style(underline=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "underline" in pt_style

    def test_rich_to_pt_style_nounderline(self):
        from rich.style import Style

        style = Style(underline=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "nounderline" in pt_style

    def test_rich_to_pt_style_strike(self):
        from rich.style import Style

        style = Style(strike=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "strike" in pt_style

    def test_rich_to_pt_style_nostrike(self):
        from rich.style import Style

        style = Style(strike=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "nostrike" in pt_style

    def test_rich_to_pt_style_italic(self):
        from rich.style import Style

        style = Style(italic=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "italic" in pt_style

    def test_rich_to_pt_style_noitalic(self):
        from rich.style import Style

        style = Style(italic=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "noitalic" in pt_style

    def test_rich_to_pt_style_blink(self):
        from rich.style import Style

        style = Style(blink=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "blink" in pt_style

    def test_rich_to_pt_style_noblink(self):
        from rich.style import Style

        style = Style(blink=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "noblink" in pt_style

    def test_rich_to_pt_style_reverse(self):
        from rich.style import Style

        style = Style(reverse=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "reverse" in pt_style

    def test_rich_to_pt_style_noreverse(self):
        from rich.style import Style

        style = Style(reverse=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "noreverse" in pt_style

    def test_rich_to_pt_style_hidden_conceal(self):
        from rich.style import Style

        style = Style(conceal=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "hidden" in pt_style

    def test_rich_to_pt_style_nohidden_conceal(self):
        from rich.style import Style

        style = Style(conceal=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "nohidden" in pt_style

    def test_rich_to_pt_style_dim(self):
        from rich.style import Style

        style = Style(dim=True)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "dim" in pt_style

    def test_rich_to_pt_style_nodim(self):
        from rich.style import Style

        style = Style(dim=False)
        pt_style = pt_utils.rich_to_pt_style(style)
        assert "nodim" in pt_style
