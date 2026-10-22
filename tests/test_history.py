"""Test history functions of cmd2"""

import argparse
import contextlib
import os
import re
import sys
import tempfile
from unittest import (
    mock,
)

import pytest

import cmd2
from cmd2.history import HistoryFormatError, HistoryIndexError

from .conftest import (
    normalize,
    run_cmd,
)


def verify_hi_last_result(app: cmd2.Cmd, expected_length: int) -> None:
    """Verifies app.last_result when it contains a dictionary of HistoryItems"""
    assert len(app.last_result) == expected_length

    # Make sure last_result items match their respective indexes in the real history
    for key in app.last_result:
        # Keys in app.last_result are 1-based indexes into the app.history list
        assert app.last_result[key] == app.history[key - 1]


#
# prompt-toolkit tests
#
def test_pt_add_history_item() -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.input import DummyInput
    from prompt_toolkit.output import DummyOutput

    # Create a history object and add some initial items
    history = InMemoryHistory()
    history.append_string("command one")
    history.append_string("command two")
    assert "command one" in history.get_strings()
    assert len(history.get_strings()) == 2

    # Start a session and use this history
    session = PromptSession(history=history, input=DummyInput(), output=DummyOutput())

    session.history.get_strings().append("new command")
    assert "new command" not in session.history.get_strings()
    assert len(history.get_strings()) == 2


#
# test History() class
#
@pytest.fixture
def hist():
    from cmd2.cmd2 import (
        History,
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    return History(
        [
            HistoryItem(Statement("", raw="first")),
            HistoryItem(Statement("", raw="second")),
            HistoryItem(Statement("", raw="third")),
            HistoryItem(Statement("", raw="fourth")),
        ]
    )


# Represents the hist fixture's JSON
hist_json = (
    "{\n"
    '  "history_version": "4.0.0",\n'
    '  "history_items": [\n'
    "    {\n"
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "first",\n'
    '        "command": "",\n'
    '        "multiline_command": false,\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "redirector": "",\n'
    '        "redirect_to": ""\n'
    "      }\n"
    "    },\n"
    "    {\n"
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "second",\n'
    '        "command": "",\n'
    '        "multiline_command": false,\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "redirector": "",\n'
    '        "redirect_to": ""\n'
    "      }\n"
    "    },\n"
    "    {\n"
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "third",\n'
    '        "command": "",\n'
    '        "multiline_command": false,\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "redirector": "",\n'
    '        "redirect_to": ""\n'
    "      }\n"
    "    },\n"
    "    {\n"
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "fourth",\n'
    '        "command": "",\n'
    '        "multiline_command": false,\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "redirector": "",\n'
    '        "redirect_to": ""\n'
    "      }\n"
    "    }\n"
    "  ]\n"
    "}"
)


@pytest.fixture
def persisted_hist():
    from cmd2.cmd2 import (
        History,
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    h = History(
        [
            HistoryItem(Statement("", raw="first")),
            HistoryItem(Statement("", raw="second")),
            HistoryItem(Statement("", raw="third")),
            HistoryItem(Statement("", raw="fourth")),
        ]
    )
    h.start_session()
    h.append(Statement("", raw="fifth"))
    h.append(Statement("", raw="sixth"))
    return h


def test_history_class_span(hist) -> None:
    span = hist.span("2..")
    assert len(span) == 3
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"

    span = hist.span("2:")
    assert len(span) == 3
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"

    span = hist.span("-2..")
    assert len(span) == 2
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"

    span = hist.span("-2:")
    assert len(span) == 2
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"

    span = hist.span("1..3")
    assert len(span) == 3
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"

    span = hist.span("1:3")
    assert len(span) == 3
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"

    span = hist.span("2:-1")
    assert len(span) == 3
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"

    span = hist.span("-3:4")
    assert len(span) == 3
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"

    span = hist.span("-4:-2")
    assert len(span) == 3
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"

    span = hist.span(":-2")
    assert len(span) == 3
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"

    span = hist.span("..-2")
    assert len(span) == 3
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"

    value_errors = ["fred", "fred:joe", "2", "-2", "a..b", "2 ..", "1 : 3", "1:0", "0:3"]
    expected_err = "History indices must be positive or negative integers, and may not be zero."
    for tryit in value_errors:
        with pytest.raises(ValueError, match=expected_err):
            hist.span(tryit)


@pytest.mark.parametrize("suffix", [":", ":999", ":-1", "..", "..999", "..-1"])
def test_history_span_past_end(hist, suffix) -> None:
    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.span(f"{len(hist) + 1}{suffix}")


@pytest.mark.parametrize(
    ("span", "indices"),
    [("4:", [4]), ("1:999", [1, 2, 3, 4]), ("-4:-1", [1, 2, 3, 4])],
)
def test_history_span_boundaries(hist, span, indices) -> None:
    assert list(hist.span(span)) == indices


@pytest.mark.parametrize("span", ["999:1", "3:1", "2:-4", "1:-999"])
def test_history_span_explicit_start_without_matches(hist, span) -> None:
    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.span(span)


@pytest.mark.parametrize("span", ["1:", "-1:"])
def test_history_span_explicit_start_on_empty_history(hist, span) -> None:
    hist.clear()
    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.span(span)


@pytest.mark.parametrize("span", [":", ".."])
@pytest.mark.parametrize("empty_history", [False, True])
def test_history_span_unbounded_without_matches(hist, span, empty_history) -> None:
    if empty_history:
        hist.clear()
    hist.start_session()
    assert hist.span(span) == {}


@pytest.mark.parametrize("span", [":-999", "..-999"])
@pytest.mark.parametrize("empty_history", [False, True])
def test_history_span_end_only_without_matches(hist, span, empty_history) -> None:
    if empty_history:
        hist.clear()
    hist.start_session()
    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.span(span)


def test_persisted_history_span(persisted_hist) -> None:
    span = persisted_hist.span("2..")
    assert len(span) == 5
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"
    assert span[5].statement.raw == "fifth"
    assert span[6].statement.raw == "sixth"

    span = persisted_hist.span("-2..")
    assert len(span) == 2
    assert span[5].statement.raw == "fifth"
    assert span[6].statement.raw == "sixth"

    span = persisted_hist.span("1..3")
    assert len(span) == 3
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"

    span = persisted_hist.span("2:-1")
    assert len(span) == 5
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"
    assert span[5].statement.raw == "fifth"
    assert span[6].statement.raw == "sixth"

    span = persisted_hist.span("-3:4")
    assert len(span) == 1
    assert span[4].statement.raw == "fourth"

    span = persisted_hist.span(":-2", include_persisted=True)
    assert len(span) == 5
    assert span[1].statement.raw == "first"
    assert span[2].statement.raw == "second"
    assert span[3].statement.raw == "third"
    assert span[4].statement.raw == "fourth"
    assert span[5].statement.raw == "fifth"

    span = persisted_hist.span(":-2", include_persisted=False)
    assert list(span) == [1, 2, 3, 4, 5]
    assert span == persisted_hist.span("1:-2")

    value_errors = ["fred", "fred:joe", "2", "-2", "a..b", "2 ..", "1 : 3", "1:0", "0:3"]
    expected_err = "History indices must be positive or negative integers, and may not be zero."
    for tryit in value_errors:
        with pytest.raises(ValueError, match=expected_err):
            persisted_hist.span(tryit)


def test_history_class_get(hist) -> None:
    assert hist.get(1).statement.raw == "first"
    assert hist.get(3).statement.raw == "third"
    assert hist.get(-2) == hist[-2]
    assert hist.get(-1).statement.raw == "fourth"
    assert hist.get(len(hist)) == hist[-1]
    assert hist.get(-len(hist)) == hist[0]

    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.get(0)

    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.get(5)


@pytest.mark.parametrize("index", [0, 5, -5, 10**100, -(10**100)])
@pytest.mark.parametrize("empty_history", [False, True])
def test_history_get_invalid_index_has_clear_error(hist, index, empty_history) -> None:
    if empty_history:
        hist.clear()
    with pytest.raises(HistoryIndexError, match="No history items in range") as error:
        hist.get(index)
    assert isinstance(error.value, IndexError)


@pytest.mark.parametrize("index", [1, -1])
def test_history_get_on_empty_history(hist, index) -> None:
    hist.clear()
    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.get(index)


def test_history_str_search(hist) -> None:
    items = hist.str_search("ir")
    assert len(items) == 2
    assert items[1].statement.raw == "first"
    assert items[3].statement.raw == "third"

    items = hist.str_search("rth")
    assert len(items) == 1
    assert items[4].statement.raw == "fourth"


def test_history_regex_search(hist) -> None:
    items = hist.regex_search("/i.*d/")
    assert len(items) == 1
    assert items[3].statement.raw == "third"

    items = hist.regex_search("s[a-z]+ond")
    assert len(items) == 1
    assert items[2].statement.raw == "second"


def test_history_max_length_zero(hist) -> None:
    hist.truncate(0)
    assert len(hist) == 0


def test_history_max_length_negative(hist) -> None:
    hist.truncate(-1)
    assert len(hist) == 0


def test_history_max_length(hist) -> None:
    hist.truncate(2)
    assert len(hist) == 2
    assert hist.get(1).statement.raw == "third"
    assert hist.get(2).statement.raw == "fourth"


def test_history_to_json(hist) -> None:
    assert hist_json == hist.to_json()


def test_history_from_json(hist) -> None:
    import json

    from cmd2.history import (
        History,
    )

    assert hist.from_json(hist_json) == hist

    # Test invalid JSON
    with pytest.raises(json.JSONDecodeError):
        hist.from_json("")

    # Send JSON with missing required element
    with pytest.raises(KeyError):
        hist.from_json("{}")

    # Create JSON with invalid history version
    backed_up_ver = History._history_version
    History._history_version = "BAD_VERSION"
    invalid_ver_json = hist.to_json()
    History._history_version = backed_up_ver

    expected_err = f"Unsupported history file version: BAD_VERSION. This application uses version {History._history_version}."
    with pytest.raises(ValueError, match=expected_err):
        hist.from_json(invalid_ver_json)


#
# test HistoryItem()
#
@pytest.fixture
def histitem():
    from cmd2.history import (
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    statement = Statement(
        "history",
        raw="help history",
        command="help",
    )
    return HistoryItem(statement)


@pytest.fixture
def parser():
    from cmd2.parsing import (
        StatementParser,
    )

    return StatementParser(
        terminators=[";", "&"],
        multiline_commands=["multiline"],
        aliases={
            "helpalias": "help",
            "42": "theanswer",
            "l": "!ls -al",
            "anothermultiline": "multiline",
            "fake": "run_pyscript",
        },
        shortcuts={"?": "help", "!": "shell"},
    )


def test_multiline_histitem(parser) -> None:
    from cmd2.history import (
        History,
    )

    line = "multiline foo\nbar\n\n"
    statement = parser.parse(line)
    history = History()
    history.append(statement)
    assert len(history) == 1
    hist_item = history[0]
    assert hist_item.raw == line
    pr_lines = hist_item.pr(1).splitlines()
    assert pr_lines[0].endswith("multiline foo bar")


def test_multiline_with_quotes_histitem(parser) -> None:
    # Test that spaces and newlines in quotes are preserved
    from cmd2.history import (
        History,
    )

    line = 'Look, "There are newlines\n  and spaces  \n "\n in\nquotes.\n;\n'
    statement = parser.parse(line)
    history = History()
    history.append(statement)
    assert len(history) == 1
    hist_item = history[0]
    assert hist_item.raw == line

    # Since spaces and newlines in quotes are preserved, this history entry spans multiple lines.
    pr_lines = hist_item.pr(1).splitlines()
    assert pr_lines[0].endswith('Look, "There are newlines')
    assert pr_lines[1] == "  and spaces  "
    assert pr_lines[2] == ' " in quotes.;'


def test_multiline_histitem_verbose(parser) -> None:
    from cmd2.history import (
        History,
    )

    line = "multiline foo\nbar\n\n"
    statement = parser.parse(line)
    history = History()
    history.append(statement)
    assert len(history) == 1
    hist_item = history[0]
    assert hist_item.raw == line
    pr_lines = hist_item.pr(1, verbose=True).splitlines()
    assert pr_lines[0].endswith("multiline foo")
    assert pr_lines[1] == "bar"


def test_single_line_format_blank(parser) -> None:
    from cmd2.history import (
        single_line_format,
    )

    line = ""
    statement = parser.parse(line)
    assert single_line_format(statement) == line


def test_history_item_instantiate() -> None:
    from cmd2.history import (
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    Statement(
        "history",
        raw="help history",
        command="help",
    )
    with pytest.raises(TypeError):
        _ = HistoryItem()


def test_history_item_properties(histitem) -> None:
    assert histitem.raw == "help history"
    assert histitem.expanded == "help history"
    assert str(histitem) == "help history"


#
# test history command
#
def test_base_history(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    out, _err = run_cmd(base_app, "history")
    expected = normalize(
        """
    1  help
    2  shortcuts
"""
    )
    assert out == expected

    out, _err = run_cmd(base_app, "history he")
    expected = normalize(
        """
    1  help
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 1)

    out, _err = run_cmd(base_app, "history sh")
    expected = normalize(
        """
    2  shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 1)


def test_history_script_format(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    out, _err = run_cmd(base_app, "history -s")
    expected = normalize(
        """
help
shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_with_string_argument(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    run_cmd(base_app, "help history")
    out, _err = run_cmd(base_app, "history help")
    expected = normalize(
        """
    1  help
    3  help history
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_expanded_with_string_argument(base_app) -> None:
    run_cmd(base_app, "alias create sc shortcuts")
    run_cmd(base_app, "help")
    run_cmd(base_app, "help history")
    run_cmd(base_app, "sc")
    out, _err = run_cmd(base_app, "history -v shortcuts")
    expected = normalize(
        """
    1  alias create sc shortcuts
    4  sc
    4x shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_expanded_with_regex_argument(base_app) -> None:
    run_cmd(base_app, "alias create sc shortcuts")
    run_cmd(base_app, "help")
    run_cmd(base_app, "help history")
    run_cmd(base_app, "sc")
    out, _err = run_cmd(base_app, "history -v /sh.*cuts/")
    expected = normalize(
        """
    1  alias create sc shortcuts
    4  sc
    4x shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_with_integer_argument(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    out, _err = run_cmd(base_app, "history 1")
    expected = normalize(
        """
    1  help
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 1)


def test_history_with_integer_span(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    run_cmd(base_app, "help history")
    out, _err = run_cmd(base_app, "history 1..2")
    expected = normalize(
        """
    1  help
    2  shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_with_span_start(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    run_cmd(base_app, "help history")
    out, _err = run_cmd(base_app, "history 2:")
    expected = normalize(
        """
    2  shortcuts
    3  help history
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_with_span_end(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    run_cmd(base_app, "help history")
    out, _err = run_cmd(base_app, "history :2")
    expected = normalize(
        """
    1  help
    2  shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


# Each of these selects nothing when history holds a single item
EMPTY_HISTORY_SPANS = ["2", "5", "999", "-2", "2:", "2:3", "2..", "2..3", "2:1", ":-999"]


@pytest.mark.parametrize(
    ("selector", "empty_selection"), [("", False), (":", False), ("..", False), (":-999", True), ("..-999", True)]
)
@pytest.mark.parametrize("empty_history", [False, True])
def test_history_selections_on_fresh_session(tmp_path, selector, empty_selection, empty_history) -> None:
    history_file = str(tmp_path / "history.dat")
    previous_app = cmd2.Cmd(persistent_history_file=history_file)
    if not empty_history:
        run_cmd(previous_app, "help")
        run_cmd(previous_app, "shortcuts")
    previous_app._persist_history()
    app = cmd2.Cmd(persistent_history_file=history_file)
    assert app.history.session_start_index == len(app.history)

    out, err = run_cmd(app, f"history {selector}")

    assert out == []
    if empty_selection:
        assert err == ["No history items in range"]
        assert app.last_result is False
    else:
        assert err == []
        assert app.last_result == {}


@pytest.mark.parametrize("action", ["--run", "--edit", "--output-file"])
@pytest.mark.parametrize(
    ("selector", "empty_history", "include_persisted"),
    [
        (selector, empty_history, include_persisted)
        for selector in ("", '""', ":", "..", '" : "', '"   "', "no_such_command", "/no_such_regex/")
        for empty_history in (False, True)
        for include_persisted in (False, True)
        if empty_history or not include_persisted or selector in ('"   "', "no_such_command", "/no_such_regex/")
    ],
)
@pytest.mark.parametrize("debug", [False, True])
def test_history_empty_actions_have_no_side_effects(
    base_app, hist, monkeypatch, tmp_path, action, selector, empty_history, include_persisted, debug
) -> None:
    base_app.history = hist
    base_app.debug = debug
    if empty_history:
        hist.clear()
    hist.start_session()
    initial_history = list(hist)
    output_file = tmp_path / "out.txt"
    output_file.write_text("old contents\n")
    missing_file = tmp_path / "missing.txt"
    mkstemp_mock = mock.MagicMock(name="mkstemp", wraps=tempfile.mkstemp)
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", mkstemp_mock)
    edit_mock = mock.MagicMock(name="run_editor")
    monkeypatch.setattr(base_app, "run_editor", edit_mock)
    run_script_mock = mock.MagicMock(name="do_run_script")
    monkeypatch.setattr(base_app, "do_run_script", run_script_mock)
    run_mock = mock.MagicMock(name="runcmds_plus_hooks")
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", run_mock)
    for target in (output_file, missing_file):
        options = f'--output-file "{target}"' if action == "--output-file" else action
        all_option = "--all" if include_persisted else ""
        _out, err = run_cmd(base_app, f"history {all_option} {options} {selector}")
        if action == "--run" and selector in ("", '""'):
            assert err == [
                "Cowardly refusing to run all previously entered commands.",
                "If this is what you want to do, specify '1:' as the range of history.",
            ]
        else:
            message = (
                "No history items in range" if selector in ("", '""', ":", "..", '" : "') else "No matching history items"
            )
            assert err == [message]
        assert base_app.last_result is False

    mkstemp_mock.assert_not_called()
    edit_mock.assert_not_called()
    run_script_mock.assert_not_called()
    run_mock.assert_not_called()
    assert output_file.read_text() == "old contents\n"
    assert not missing_file.exists()
    assert list(hist) == initial_history


@pytest.mark.parametrize("action", ["--run", "--edit", "--output-file"])
@pytest.mark.parametrize("selector", [":", "..", '" : "', "first", "/first/"])
@pytest.mark.parametrize("include_persisted", [False, True])
def test_history_nonempty_actions_are_preserved(
    base_app, hist, monkeypatch, tmp_path, action, selector, include_persisted
) -> None:
    base_app.history = hist
    if include_persisted:
        hist.start_session()
    expected = list(hist[:1] if selector in ("first", "/first/") else hist)
    expected_text = "".join(f"{item.raw}\n" for item in expected)
    output_file = tmp_path / "out.txt"
    output_file.write_text("old contents\n")
    run_mock = mock.Mock(return_value=False)
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", run_mock)
    edited = []

    def fake_editor(fname) -> None:
        with open(fname) as script:
            edited.append(script.read())

    monkeypatch.setattr(base_app, "run_editor", fake_editor)
    run_script_mock = mock.Mock()
    monkeypatch.setattr(base_app, "do_run_script", run_script_mock)
    options = f'--output-file "{output_file}"' if action == "--output-file" else action
    all_option = "--all" if include_persisted else ""

    _out, err = run_cmd(base_app, f"history {all_option} {options} {selector}")

    assert err == []
    if action == "--run":
        run_mock.assert_called_once_with(expected)
        assert base_app.last_result is True
    elif action == "--edit":
        assert edited == [expected_text]
        run_script_mock.assert_called_once()
    else:
        assert output_file.read_text() == expected_text
        assert base_app.last_result is True


@pytest.mark.parametrize("action", ["--run", "--edit", "--output-file"])
def test_history_unbounded_empty_action_after_reload(base_app, monkeypatch, tmp_path, action) -> None:
    history_file = tmp_path / "history.dat"
    base_app.persistent_history_file = str(history_file)
    run_cmd(base_app, "help")
    base_app._persist_history()
    base_app._initialize_history(str(history_file))
    assert len(base_app.history) == base_app.history.session_start_index == 1
    output_file = tmp_path / "out.txt"
    output_file.write_text("keep me\n")
    mkstemp_mock = mock.Mock(wraps=tempfile.mkstemp)
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", mkstemp_mock)
    editor = mock.Mock()
    replay = mock.Mock()
    monkeypatch.setattr(base_app, "run_editor", editor)
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", replay)
    options = f'--output-file "{output_file}"' if action == "--output-file" else action

    out, err = run_cmd(base_app, f"history {options} :")

    assert out == []
    assert err == ["No history items in range"]
    assert base_app.last_result is False
    assert output_file.read_text() == "keep me\n"
    mkstemp_mock.assert_not_called()
    editor.assert_not_called()
    replay.assert_not_called()


@pytest.mark.parametrize("span", [":2", "..2", "..-3"])
def test_history_end_only_with_all_includes_persisted(base_app, hist, span) -> None:
    base_app.history = hist
    hist.start_session()

    out, err = run_cmd(base_app, f"history --all {span}")

    assert len(out) == 2
    assert err == []
    assert list(base_app.last_result) == [1, 2]


@pytest.mark.parametrize(
    ("span", "session_start"),
    [(span, start) for span in ("3:1", "2:-4", "1:-999", ":-999", "..-999", "-5:", "-5..4", "-999:") for start in (0, 2, 4)],
)
@pytest.mark.parametrize("action", ["", "--run", "--edit", "--output-file"])
@pytest.mark.parametrize("debug", [False, True])
def test_history_empty_bounded_span_has_no_side_effects(
    base_app, hist, monkeypatch, tmp_path, span, session_start, action, debug
) -> None:
    base_app.history = hist
    hist.session_start_index = session_start
    base_app.debug = debug
    mkstemp_mock = mock.MagicMock(name="mkstemp")
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", mkstemp_mock)
    edit_mock = mock.MagicMock(name="run_editor")
    monkeypatch.setattr(base_app, "run_editor", edit_mock)
    run_script_mock = mock.MagicMock(name="do_run_script")
    monkeypatch.setattr(base_app, "do_run_script", run_script_mock)
    run_mock = mock.MagicMock(name="runcmds_plus_hooks")
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", run_mock)
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("keep me\n")
    missing_file = tmp_path / "missing.txt"

    for output_file in (existing_file, missing_file):
        options = f'--output-file "{output_file}"' if action == "--output-file" else action
        out, err = run_cmd(base_app, f"history {options} -- {span}")
        assert out == []
        assert err == ["No history items in range"]
        assert base_app.last_result is False

    mkstemp_mock.assert_not_called()
    edit_mock.assert_not_called()
    run_script_mock.assert_not_called()
    run_mock.assert_not_called()
    assert len(base_app.history) == 4
    assert existing_file.read_text() == "keep me\n"
    assert not missing_file.exists()


@pytest.fixture
def debug_history_app(base_app) -> cmd2.Cmd:
    """App whose only history item is 'set debug true', with debug reset so a rerun is detectable"""
    run_cmd(base_app, "set debug true")
    assert len(base_app.history) == 1
    base_app.debug = False
    return base_app


@pytest.mark.parametrize("span", EMPTY_HISTORY_SPANS)
def test_history_empty_span(debug_history_app, span) -> None:
    out, err = run_cmd(debug_history_app, f"history {span}")

    assert out == []
    assert err == ["No history items in range"]
    assert debug_history_app.last_result is False


@pytest.mark.parametrize("span", EMPTY_HISTORY_SPANS)
def test_history_run_empty_span(debug_history_app, span) -> None:
    out, err = run_cmd(debug_history_app, f"history --run {span}")

    assert out == []
    assert err == ["No history items in range"]
    assert debug_history_app.last_result is False
    assert debug_history_app.debug is False
    assert len(debug_history_app.history) == 1


@pytest.mark.parametrize("span", EMPTY_HISTORY_SPANS)
def test_history_edit_empty_span(debug_history_app, monkeypatch, span) -> None:
    mkstemp_mock = mock.MagicMock(name="mkstemp", wraps=tempfile.mkstemp)
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", mkstemp_mock)
    edit_mock = mock.MagicMock(name="run_editor")
    monkeypatch.setattr("cmd2.Cmd.run_editor", edit_mock)
    run_script_mock = mock.MagicMock(name="do_run_script")
    monkeypatch.setattr("cmd2.Cmd.do_run_script", run_script_mock)

    out, err = run_cmd(debug_history_app, f"history --edit {span}")

    assert out == []
    assert err == ["No history items in range"]
    assert debug_history_app.last_result is False
    mkstemp_mock.assert_not_called()
    edit_mock.assert_not_called()
    run_script_mock.assert_not_called()
    assert debug_history_app.debug is False


@pytest.mark.parametrize("span", EMPTY_HISTORY_SPANS)
def test_history_output_file_empty_span(debug_history_app, tmp_path, span) -> None:
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("keep me\n")
    missing_file = tmp_path / "missing.txt"

    for output_file in (existing_file, missing_file):
        out, err = run_cmd(debug_history_app, f'history --output-file "{output_file}" {span}')

        assert out == []
        assert err == ["No history items in range"]
        assert debug_history_app.last_result is False

    assert existing_file.read_text() == "keep me\n"
    assert not missing_file.exists()


@pytest.mark.parametrize("action", ["", "--run", "--edit", "--output-file"])
def test_history_index_past_end_with_three_items(base_app, monkeypatch, tmp_path, action) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    run_cmd(base_app, "set debug true")
    base_app.debug = False
    edit_mock = mock.MagicMock(name="run_editor")
    monkeypatch.setattr("cmd2.Cmd.run_editor", edit_mock)
    output_file = tmp_path / "existing.txt"
    output_file.write_text("keep me\n")
    if action == "--output-file":
        action = f'--output-file "{output_file}"'

    out, err = run_cmd(base_app, f"history {action} 5")

    assert out == []
    assert err == ["No history items in range"]
    assert base_app.last_result is False
    assert len(base_app.history) == 3
    assert base_app.debug is False
    edit_mock.assert_not_called()
    assert output_file.read_text() == "keep me\n"


@pytest.mark.parametrize("span", ["1", "-1", "1:", "-1:"])
def test_history_run_valid_span(debug_history_app, span) -> None:
    _out, err = run_cmd(debug_history_app, f"history --run -- {span}")

    assert err == []
    assert debug_history_app.last_result is True
    assert debug_history_app.debug is True


@pytest.mark.parametrize("span", ["1", "-1", "1:", "-1:"])
def test_history_output_file_valid_span(debug_history_app, tmp_path, span) -> None:
    output_file = tmp_path / "out.txt"
    output_file.write_text("old contents\n")

    _out, err = run_cmd(debug_history_app, f'history --output-file "{output_file}" -- {span}')

    assert err == []
    assert debug_history_app.last_result is True
    assert output_file.read_text() == "set debug true\n"


@pytest.mark.parametrize("span", ["1", "-1", "1:"])
def test_history_edit_valid_span(debug_history_app, monkeypatch, span) -> None:
    edited = []

    def fake_editor(_self, fname) -> None:
        with open(fname) as f:
            edited.append(f.read())

    monkeypatch.setattr("cmd2.Cmd.run_editor", fake_editor)
    run_script_mock = mock.MagicMock(name="do_run_script")
    monkeypatch.setattr("cmd2.Cmd.do_run_script", run_script_mock)

    _out, err = run_cmd(debug_history_app, f"history --edit -- {span}")

    assert err == []
    assert edited == ["set debug true\n"]
    run_script_mock.assert_called_once()


@pytest.mark.parametrize("search", ["no_such_command", "/no_such_regex/"])
def test_history_search_without_match_is_not_an_error(debug_history_app, search) -> None:
    out, err = run_cmd(debug_history_app, f"history {search}")

    assert out == []
    assert err == []
    assert debug_history_app.last_result == {}


@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("selector", ["0", "-0"])
def test_history_index_zero_has_clean_error(debug_history_app, debug, selector) -> None:
    debug_history_app.debug = debug
    out, err = run_cmd(debug_history_app, f"history {selector}")
    assert out == []
    assert err == ["No history items in range. The first command in history is command 1."]
    assert debug_history_app.last_result is False


@pytest.mark.parametrize("selector", ["1", "1:"])
@pytest.mark.parametrize("debug", [False, True])
def test_history_does_not_hide_unexpected_index_errors(base_app, hist, monkeypatch, selector, debug) -> None:
    base_app.history = hist
    base_app.debug = debug
    monkeypatch.setattr(type(hist), "__getitem__", mock.Mock(side_effect=IndexError("unexpected lookup failure")))

    with pytest.raises(IndexError, match="unexpected lookup failure"):
        base_app.onecmd(f"history {selector}")

    out, err = run_cmd(base_app, f"history {selector}")
    assert out == []
    assert err != ["No history items in range"]
    assert any("unexpected lookup failure" in line for line in err)


def test_history_literal_search_containing_colon(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "help history")
    run_cmd(base_app, "!ls -hal :")
    out, err = run_cmd(base_app, 'history "hal :"')
    assert err == []
    assert out == ["    3  !ls -hal :"]
    assert list(base_app.last_result) == [3]


@pytest.mark.parametrize("separator", [":", ".."])
@pytest.mark.parametrize("session_start", [0, 2, 4])
@pytest.mark.parametrize("include_persisted", [False, True])
@pytest.mark.parametrize(("end", "expected"), [("2", [1, 2]), ("-3", [1, 2]), ("4", [1, 2, 3, 4]), ("999", [1, 2, 3, 4])])
def test_history_bounded_ranges_use_absolute_indices(hist, separator, session_start, include_persisted, end, expected) -> None:
    hist.session_start_index = session_start
    assert list(hist.span(f"{separator}{end}", include_persisted)) == expected
    assert list(hist.span(f"1{separator}{end}", include_persisted)) == expected
    assert list(hist.span(f"-4{separator}{end}", include_persisted)) == expected
    assert list(hist.span(separator, include_persisted)) == list(range(1 if include_persisted else session_start + 1, 5))


@pytest.mark.parametrize("selector", [":2", "..2", "1:2", "1..2", ":-1", "..-1", "-2:", "-2.."])
@pytest.mark.parametrize("action", ["", "--run", "--edit", "--output-file"])
@pytest.mark.parametrize("include_persisted", [False, True])
def test_history_bounded_actions_after_reload(base_app, monkeypatch, tmp_path, selector, action, include_persisted) -> None:
    base_app.persistent_history_file = str(tmp_path / "history.dat")
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    base_app._persist_history()
    base_app._initialize_history(base_app.persistent_history_file)
    assert base_app.history.session_start_index == len(base_app.history) == 2
    expected = list(base_app.history)
    expected_text = "help\nshortcuts\n"
    output_file = tmp_path / "commands.txt"
    replay = mock.Mock(return_value=False)
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", replay)
    edited = []

    def fake_editor(fname) -> None:
        with open(fname) as script:
            edited.append(script.read())

    monkeypatch.setattr(base_app, "run_editor", fake_editor)
    run_script = mock.Mock()
    monkeypatch.setattr(base_app, "do_run_script", run_script)
    options = f'--output-file "{output_file}"' if action == "--output-file" else action
    all_option = "--all" if include_persisted else ""
    out, err = run_cmd(base_app, f"history {all_option} {options} -- {selector}")
    if action in ("--run", "--edit") and not include_persisted:
        assert out == []
        assert err == ["Use --all to run or edit commands from previous sessions."]
        assert base_app.last_result is False
        replay.assert_not_called()
        run_script.assert_not_called()
        assert edited == []
        assert not output_file.exists()
        return
    assert err == []
    if action == "--run":
        replay.assert_called_once_with(expected)
        assert base_app.last_result is True
    elif action == "--edit":
        assert edited == [expected_text]
        run_script.assert_called_once()
    elif action == "--output-file":
        assert output_file.read_text() == expected_text
        assert base_app.last_result is True
    else:
        assert out == ["    1  help", "    2  shortcuts"]
        assert base_app.last_result == {1: expected[0], 2: expected[1]}


@pytest.mark.parametrize("selector", ["0", "-0", "0:2", "0:", "1:0", ":0", "-0..2", "..0"])
@pytest.mark.parametrize("action", ["", "--run", "--edit", "--output-file"])
@pytest.mark.parametrize("debug", [False, True])
def test_history_invalid_selection_has_no_side_effects(base_app, monkeypatch, tmp_path, selector, action, debug) -> None:
    run_cmd(base_app, "help")
    base_app.debug = debug
    original_history = list(base_app.history)
    effects = [mock.Mock() for _ in range(4)]
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", effects[0])
    monkeypatch.setattr(base_app, "run_editor", effects[1])
    monkeypatch.setattr(base_app, "do_run_script", effects[2])
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", effects[3])
    existing = tmp_path / "existing.txt"
    existing.write_text("keep me\n")
    missing = tmp_path / "missing.txt"
    for target in (existing, missing):
        options = f'--output-file "{target}"' if action == "--output-file" else action
        out, err = run_cmd(base_app, f"history {options} -- {selector}")
        assert out == []
        message = (
            "No history items in range."
            if selector in ("0", "-0")
            else ("History indices must be positive or negative integers, and may not be zero.")
        )
        assert " ".join(err) == f"{message} The first command in history is command 1."
        assert base_app.last_result is False
    for effect in effects:
        effect.assert_not_called()
    assert existing.read_text() == "keep me\n"
    assert not missing.exists()
    assert list(base_app.history) == original_history


@pytest.mark.parametrize("selector", ["0:2", "0:", "1:0", "1:2:3"])
def test_history_invalid_range_preserves_value_error_api(hist, selector) -> None:
    with pytest.raises(HistoryFormatError) as error:
        hist.span(selector)
    assert isinstance(error.value, ValueError)


@pytest.mark.parametrize(("index", "expected"), [(-1, 4), (-2, 3), (-4, 1)])
@pytest.mark.parametrize("session_start", [0, 2, 4])
def test_history_negative_index_uses_positive_key(base_app, hist, index, expected, session_start) -> None:
    base_app.history = hist
    hist.session_start_index = session_start
    out, err = run_cmd(base_app, f"history {index}")
    assert err == []
    assert out == [f" {expected:>4}  {hist[expected - 1].raw}"]
    assert base_app.last_result == {expected: hist[expected - 1]}


@pytest.mark.parametrize("selector", ["/[/", "no_such_command"])
def test_history_does_not_hide_search_errors(base_app, monkeypatch, selector) -> None:
    if selector == "no_such_command":
        monkeypatch.setattr(base_app.history, "str_search", mock.Mock(side_effect=ValueError("unexpected search failure")))
        error = ValueError
    else:
        error = re.error
    with pytest.raises(error):
        base_app.onecmd(f"history -r {selector}")
    assert base_app.last_result is False


@pytest.mark.parametrize("selector", ["-5:", "-5:-1", "-5:3", "-5..", "-5..-1", "-999:"])
def test_history_span_rejects_overly_negative_starts(hist, selector) -> None:
    with pytest.raises(HistoryIndexError, match="No history items in range"):
        hist.span(selector)


@pytest.mark.parametrize(
    ("selector", "needle"),
    [
        ("/a..b/", "axxb"),
        ("/one:/", "one:"),
        ("http://x", "http://x"),
        ("a:b", "a:b"),
        ("1:2:3", "1:2:3"),
        ("abc:", "abc:"),
        ("1_0", "1_0"),
        ("+1", "+1"),
        ('" 1 "', " 1 "),
        ("\u0661", "\u0661"),
        ("1\u0661", "1\u0661"),
        ("-\u0661", "-\u0661"),
    ],
)
def test_history_search_dispatch_is_not_numeric_or_range(base_app, hist, selector, needle) -> None:
    hist.clear()
    for index in range(10):
        text = f"help before{needle}after" if index == 2 else "help control"
        hist.append(base_app.statement_parser.parse(text))
    base_app.history = hist

    out, err = run_cmd(base_app, f"history -- {selector}")

    assert err == []
    assert out == [f"    3  help before{needle}after"]
    assert base_app.last_result == {3: hist[2]}


@pytest.mark.parametrize("selector", ["", ":", "no_such_command", "/no_such_regex/"])
def test_get_history_returns_empty_dictionary_for_actions(base_app, selector) -> None:
    args = argparse.Namespace(arg=selector, all=False, run=False, edit=True, output_file=None)
    assert base_app._get_history(args) == {}


@pytest.mark.parametrize("selector", ["1:2:3", "abc:", "a:b", "\u0661:2", "1\u0661:2", "+1:2", "1_0:2"])
def test_history_format_error_does_not_suggest_command_one(hist, selector) -> None:
    with pytest.raises(HistoryFormatError) as error:
        hist.span(selector)
    assert "The first command" not in str(error.value)


@pytest.mark.parametrize("selector", ["0:2", "1:0", "-0..2", "..-0"])
def test_history_zero_endpoint_has_command_one_hint(hist, selector) -> None:
    with pytest.raises(HistoryFormatError) as error:
        hist.span(selector)
    assert "The first command in history is command 1." in str(error.value)


@pytest.mark.parametrize("selector", ["1", "-6", ":2", "1:5", "2:", "-6:-1", "4", "-3", "4:5"])
@pytest.mark.parametrize("action", ["--run", "--edit"])
def test_history_persisted_actions_require_all(base_app, persisted_hist, monkeypatch, selector, action) -> None:
    base_app.history = persisted_hist
    effects = [mock.Mock() for _ in range(4)]
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", effects[0])
    monkeypatch.setattr(base_app, "run_editor", effects[1])
    monkeypatch.setattr(base_app, "do_run_script", effects[2])
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", effects[3])

    out, err = run_cmd(base_app, f"history {action} -- {selector}")

    assert out == []
    assert err == ["Use --all to run or edit commands from previous sessions."]
    assert base_app.last_result is False
    for effect in effects:
        effect.assert_not_called()


@pytest.mark.parametrize("selector", ["5", "-2", "5:", "-2:"])
@pytest.mark.parametrize("action", ["--run", "--edit"])
def test_history_current_session_actions_do_not_require_all(base_app, persisted_hist, monkeypatch, selector, action) -> None:
    base_app.history = persisted_hist
    expected = list(persisted_hist[4:5] if selector in ("5", "-2") else persisted_hist[4:])
    replay = mock.Mock(return_value=False)
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", replay)
    edited = []

    def fake_editor(fname) -> None:
        with open(fname) as script:
            edited.append(script.read())

    monkeypatch.setattr(base_app, "run_editor", fake_editor)
    run_script = mock.Mock()
    monkeypatch.setattr(base_app, "do_run_script", run_script)

    _out, err = run_cmd(base_app, f"history {action} -- {selector}")

    assert err == []
    if action == "--run":
        replay.assert_called_once_with(expected)
    else:
        assert edited == ["".join(f"{item.raw}\n" for item in expected)]
        run_script.assert_called_once()


@pytest.mark.parametrize("sign", ["", "-"])
@pytest.mark.parametrize("action", ["", "--run", "--edit", "--output-file"])
@pytest.mark.parametrize("debug", [False, True])
def test_history_integer_conversion_limit_has_no_side_effects(
    base_app, hist, monkeypatch, tmp_path, sign, action, debug
) -> None:
    base_app.history = hist
    base_app.debug = debug
    effects = [mock.Mock() for _ in range(4)]
    monkeypatch.setattr("cmd2.cmd2.tempfile.mkstemp", effects[0])
    monkeypatch.setattr(base_app, "run_editor", effects[1])
    monkeypatch.setattr(base_app, "do_run_script", effects[2])
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", effects[3])
    output_file = tmp_path / "existing.txt"
    output_file.write_text("keep me\n")
    options = f'--output-file "{output_file}"' if action == "--output-file" else action
    limit = sys.int_info.str_digits_check_threshold
    selector = sign + "9" * (limit + 1)
    original_limit = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(limit)
        out, err = run_cmd(base_app, f"history {options} -- {selector}")
    finally:
        sys.set_int_max_str_digits(original_limit)

    assert out == []
    assert err == ["No history items in range"]
    assert base_app.last_result is False
    for effect in effects:
        effect.assert_not_called()
    assert output_file.read_text() == "keep me\n"
    assert len(base_app.history) == 4


def test_history_help_explains_selection_and_persisted_actions(base_app) -> None:
    out, err = run_cmd(base_app, "help history")
    text = " ".join(out)
    assert err == []
    assert "current session" in text
    assert "full history" in text
    assert "required to run or edit" in text


def test_history_output_file() -> None:
    app = cmd2.Cmd(multiline_commands=["alias"])
    run_cmd(app, "help")
    run_cmd(app, "shortcuts")
    run_cmd(app, "help history")
    run_cmd(app, "alias create my_alias history;")

    fd, fname = tempfile.mkstemp(prefix="", suffix=".txt")
    os.close(fd)
    run_cmd(app, f'history -o "{fname}"')
    assert app.last_result is True

    expected = normalize("help\nshortcuts\nhelp history\nalias create my_alias history;")
    with open(fname) as f:
        content = normalize(f.read())
    assert content == expected


def test_history_bad_output_file(base_app) -> None:
    run_cmd(base_app, "help")
    run_cmd(base_app, "shortcuts")
    run_cmd(base_app, "help history")

    fname = os.path.join(os.path.sep, "fake", "fake", "fake")
    out, err = run_cmd(base_app, f'history -o "{fname}"')

    assert not out
    assert "Error saving" in err[0]
    assert base_app.last_result is False


def test_history_edit(monkeypatch) -> None:
    app = cmd2.Cmd(multiline_commands=["alias"])

    # Set a fake editor just to make sure we have one.  We aren't really
    # going to call it due to the mock
    app.editor = "fooedit"

    # Mock out the run_editor call so we don't actually open an editor
    edit_mock = mock.MagicMock(name="run_editor")
    monkeypatch.setattr("cmd2.Cmd.run_editor", edit_mock)

    # Mock out the run_script call since the mocked edit won't produce a file
    run_script_mock = mock.MagicMock(name="do_run_script")
    monkeypatch.setattr("cmd2.Cmd.do_run_script", run_script_mock)

    # Put commands in history
    run_cmd(app, "help")
    run_cmd(app, "alias create my_alias history;")

    run_cmd(app, "history -e 1:2")

    # Make sure both functions were called
    edit_mock.assert_called_once()
    run_script_mock.assert_called_once()


def test_history_run_all_commands(base_app) -> None:
    # make sure we refuse to run all commands as a default
    run_cmd(base_app, "shortcuts")
    out, err = run_cmd(base_app, "history -r")

    assert not out
    assert err[0].startswith("Cowardly refusing to run all")
    assert base_app.last_result is False


def test_history_run_one_command(base_app) -> None:
    out1, _err1 = run_cmd(base_app, "help")
    out2, _err2 = run_cmd(base_app, "history -r 1")
    assert out1 == out2
    assert base_app.last_result is True


def test_history_clear(mocker, hist_file) -> None:
    # Add commands to history
    app = cmd2.Cmd(persistent_history_file=hist_file)
    run_cmd(app, "help")
    run_cmd(app, "alias")

    # Make sure history has items
    out, err = run_cmd(app, "history")
    assert out
    verify_hi_last_result(app, 2)

    # Clear the history
    run_cmd(app, "history --clear")
    assert app.last_result is True

    # Make sure history is empty and its file is gone
    out, err = run_cmd(app, "history")
    assert out == []
    assert not os.path.exists(hist_file)
    verify_hi_last_result(app, 0)

    # Clear the history again and make sure the FileNotFoundError from trying to delete missing history file is silent
    run_cmd(app, "history --clear")
    assert app.last_result is True

    # Cause os.remove to fail and make sure error gets printed
    mock_remove = mocker.patch("os.remove")
    mock_remove.side_effect = OSError

    out, err = run_cmd(app, "history --clear")
    assert out == []
    assert "Error removing history file" in err[0]
    assert app.last_result is False


def test_history_verbose_with_other_options(base_app) -> None:
    # make sure -v shows a usage error if any other options are present
    options_to_test = ["-r", "-e", "-o file", "-c", "-x"]
    for opt in options_to_test:
        out, _err = run_cmd(base_app, "history -v " + opt)
        assert "-v cannot be used with any other options" in out
        assert base_app.last_result is False


def test_history_verbose(base_app) -> None:
    # validate function of -v option
    run_cmd(base_app, "alias create s shortcuts")
    run_cmd(base_app, "s")
    out, _err = run_cmd(base_app, "history -v")

    expected = normalize(
        """
    1  alias create s shortcuts
    2  s
    2x shortcuts
"""
    )
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_script_with_invalid_options(base_app) -> None:
    # make sure -s shows a usage error if -c, -r, -e, or -o are present
    options_to_test = ["-r", "-e", "-o file", "-c"]
    for opt in options_to_test:
        out, _err = run_cmd(base_app, "history -s " + opt)
        assert "-s and -x cannot be used with -c, -r, -e, or -o" in out
        assert base_app.last_result is False


def test_history_script(base_app) -> None:
    cmds = ["alias create s shortcuts", "s"]
    for cmd in cmds:
        run_cmd(base_app, cmd)
    out, _err = run_cmd(base_app, "history -s")
    assert out == cmds
    verify_hi_last_result(base_app, 2)


def test_history_expanded_with_invalid_options(base_app) -> None:
    # make sure -x shows a usage error if -c, -r, -e, or -o are present
    options_to_test = ["-r", "-e", "-o file", "-c"]
    for opt in options_to_test:
        out, _err = run_cmd(base_app, "history -x " + opt)
        assert "-s and -x cannot be used with -c, -r, -e, or -o" in out
        assert base_app.last_result is False


def test_history_expanded(base_app) -> None:
    # validate function of -x option
    cmds = ["alias create s shortcuts", "s"]
    for cmd in cmds:
        run_cmd(base_app, cmd)
    out, _err = run_cmd(base_app, "history -x")
    expected = ["    1  alias create s shortcuts", "    2  shortcuts"]
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_history_script_expanded(base_app) -> None:
    # validate function of -s -x options together
    cmds = ["alias create s shortcuts", "s"]
    for cmd in cmds:
        run_cmd(base_app, cmd)
    out, _err = run_cmd(base_app, "history -sx")
    expected = ["alias create s shortcuts", "shortcuts"]
    assert out == expected
    verify_hi_last_result(base_app, 2)


def test_exclude_from_history(base_app) -> None:
    # Run history command
    run_cmd(base_app, "history")
    verify_hi_last_result(base_app, 0)

    # Verify that the history is empty
    out, _err = run_cmd(base_app, "history")
    assert out == []
    verify_hi_last_result(base_app, 0)

    # Now run a command which isn't excluded from the history
    run_cmd(base_app, "help")

    # And verify we have a history now ...
    out, _err = run_cmd(base_app, "history")
    expected = normalize("""    1  help""")
    assert out == expected
    verify_hi_last_result(base_app, 1)


#
# test history initialization
#
@pytest.fixture(scope="session")
def hist_file():
    fd, filename = tempfile.mkstemp(prefix="hist_file", suffix=".dat")
    os.close(fd)
    yield filename
    # teardown code
    with contextlib.suppress(FileNotFoundError):
        os.remove(filename)


def test_history_file_is_directory(capsys) -> None:
    with tempfile.TemporaryDirectory() as test_dir:
        # Create a new cmd2 app
        cmd2.Cmd(persistent_history_file=test_dir)
        _, err = capsys.readouterr()
        assert "is a directory" in err


def test_history_can_create_directory(mocker) -> None:
    # Mock out atexit.register so the persistent file doesn't written when this function
    # exists because we will be deleting the directory it needs to go to.
    mocker.patch("atexit.register")

    # Create a temp path for us to use and let it get deleted
    with tempfile.TemporaryDirectory() as test_dir:
        pass
    assert not os.path.isdir(test_dir)

    # Add some subdirectories for the complete history file directory
    hist_file_dir = os.path.join(test_dir, "subdir1", "subdir2")
    hist_file = os.path.join(hist_file_dir, "hist_file")

    # Make sure cmd2 creates the history file directory
    cmd2.Cmd(persistent_history_file=hist_file)
    assert os.path.isdir(hist_file_dir)

    # Cleanup
    os.rmdir(hist_file_dir)


def test_history_cannot_create_directory(mocker, capsys) -> None:
    mock_open = mocker.patch("os.makedirs")
    mock_open.side_effect = OSError

    hist_file_path = os.path.join("fake_dir", "file")
    cmd2.Cmd(persistent_history_file=hist_file_path)
    _, err = capsys.readouterr()
    assert "Error creating persistent history file directory" in err


def test_history_file_permission_error(mocker, capsys, tmp_path) -> None:
    mock_open = mocker.patch("builtins.open")
    mock_open.side_effect = PermissionError

    # A path under tmp_path rather than a fixed one: mocking open() does not stop the history setup from creating the file's
    # parent directory, and a fixed path would leave that directory behind as a side effect other tests could come to depend
    # on.
    cmd2.Cmd(persistent_history_file=str(tmp_path / "doesntmatter"))
    out, err = capsys.readouterr()
    assert not out
    assert "Cannot read persistent history file" in err


def test_history_file_bad_compression(capsys, tmp_path) -> None:
    history_file = tmp_path / "doesntmatter"
    history_file.write_bytes(b"THIS IS NOT COMPRESSED DATA")

    cmd2.Cmd(persistent_history_file=str(history_file))
    out, err = capsys.readouterr()
    assert not out
    assert "Error decompressing persistent history data" in err


def test_history_file_bad_json(capsys, tmp_path) -> None:
    import lzma

    data = b"THIS IS NOT JSON"
    compressed_data = lzma.compress(data)

    history_file = tmp_path / "doesntmatter"
    history_file.write_bytes(compressed_data)

    cmd2.Cmd(persistent_history_file=str(history_file))
    out, err = capsys.readouterr()
    assert not out
    assert "Error processing persistent history data" in err


def test_history_populates_pt(hist_file) -> None:
    # - create a cmd2 with persistent history
    app = cmd2.Cmd(persistent_history_file=hist_file)
    run_cmd(app, "help")
    run_cmd(app, "shortcuts")
    run_cmd(app, "shortcuts")
    run_cmd(app, "alias")
    # call the private method which is registered to write history at exit
    app._persist_history()

    # see if history came back
    app = cmd2.Cmd(persistent_history_file=hist_file)
    assert len(app.history) == 4
    assert app.history.get(1).statement.raw == "help"
    assert app.history.get(2).statement.raw == "shortcuts"
    assert app.history.get(3).statement.raw == "shortcuts"
    assert app.history.get(4).statement.raw == "alias"

    # prompt-toolkit only adds a single entry for multiple sequential identical commands
    # so we check to make sure that cmd2 populated the prompt-toolkit history
    # using the same rules
    pt_history = app.main_session.history.get_strings()
    assert len(pt_history) == 3
    assert pt_history[0] == "help"
    assert pt_history[1] == "shortcuts"
    assert pt_history[2] == "alias"


#
# test cmd2's ability to write out history on exit
# we are testing the _persist_history() method, and
# we assume that the atexit module will call this method
# properly
#
def test_persist_history_ensure_no_error_if_no_histfile(base_app, capsys) -> None:
    # make sure if there is no persistent history file and someone
    # calls the private method call that we don't get an error
    base_app._persist_history()
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_persist_history_permission_error(hist_file, mocker, capsys) -> None:
    app = cmd2.Cmd(persistent_history_file=hist_file)
    run_cmd(app, "help")
    mock_open = mocker.patch("builtins.open")
    mock_open.side_effect = PermissionError
    app._persist_history()
    out, err = capsys.readouterr()
    assert not out
    assert "Cannot write persistent history file" in err
