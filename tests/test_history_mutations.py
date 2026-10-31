"""Session membership survives structural changes to the public history list."""

import copy
import pickle
from unittest import mock

import pytest

from cmd2.history import History, HistoryItem
from cmd2.parsing import Statement

from .conftest import run_cmd


def item(raw):
    return HistoryItem(Statement("", raw=raw))


@pytest.fixture
def history():
    """Four persisted entries (old-0..old-3) followed by two current-session entries (new-0, new-1)."""
    hist = History(item(f"old-{i}") for i in range(4))
    hist.start_session()
    hist.extend(item(f"new-{i}") for i in range(2))
    return hist


def current_session(hist):
    """Return current-session entries as {1-based index: raw}, checking every session-aware query agrees.

    Also checks session_start_index: every entry from it on is current, and the entry before it is persisted.
    """
    by_span = {index: entry.raw for index, entry in hist.span(":").items()}
    assert {index: entry.raw for index, entry in hist.str_search("-").items()} == by_span
    assert {index: entry.raw for index, entry in hist.regex_search(".*").items()} == by_span
    start = hist.session_start_index
    assert not any(hist.is_persisted(entry) for entry in hist[start:])
    assert start == 0 or hist.is_persisted(hist[start - 1])
    return by_span


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, {4: "new-0", 5: "new-1"}),
        (-6, {4: "new-0", 5: "new-1"}),
        (-1, {5: "new-0"}),
        (slice(None, 2), {3: "new-0", 4: "new-1"}),
        (slice(2, 5), {3: "new-1"}),
        (slice(None, None, 2), {3: "new-1"}),
        (slice(None, None, -2), {3: "new-0"}),
        (slice(5, 1, -2), {4: "new-0"}),
        (slice(None), {}),
        (slice(1, 1), {5: "new-0", 6: "new-1"}),
    ],
)
def test_delete_keeps_membership_of_remaining_entries(history, index, expected):
    del history[index]
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("index", "removed", "expected"),
    [
        (0, "old-0", {4: "new-0", 5: "new-1"}),
        (-3, "old-3", {4: "new-0", 5: "new-1"}),
        (-1, "new-1", {5: "new-0"}),
    ],
)
def test_pop_keeps_membership_of_remaining_entries(history, index, removed, expected):
    assert history.pop(index).raw == removed
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("old-1", {4: "new-0", 5: "new-1"}), ("new-1", {5: "new-0"})],
)
def test_remove_keeps_membership_of_remaining_entries(history, raw, expected):
    assert history.remove(item(raw)) is None
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, {1: "inserted-0", 6: "new-0", 7: "new-1"}),
        (3, {4: "inserted-0", 6: "new-0", 7: "new-1"}),
        (-3, {4: "inserted-0", 6: "new-0", 7: "new-1"}),
        (-99, {1: "inserted-0", 6: "new-0", 7: "new-1"}),
        (4, {5: "inserted-0", 6: "new-0", 7: "new-1"}),
        (99, {5: "new-0", 6: "new-1", 7: "inserted-0"}),
        (-1, {5: "new-0", 6: "inserted-0", 7: "new-1"}),
    ],
)
def test_inserted_entry_is_current_wherever_it_goes(history, index, expected):
    history.insert(index, item("inserted-0"))
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("index", "count", "expected"),
    [
        (slice(0, 1), 2, {1: "replacement-0", 2: "replacement-1", 6: "new-0", 7: "new-1"}),
        (slice(1, 3), 0, {3: "new-0", 4: "new-1"}),
        (slice(2, 5), 2, {3: "replacement-0", 4: "replacement-1", 5: "new-1"}),
        (
            slice(2, 5),
            4,
            {3: "replacement-0", 4: "replacement-1", 5: "replacement-2", 6: "replacement-3", 7: "new-1"},
        ),
        (slice(4, 5), 2, {5: "replacement-0", 6: "replacement-1", 7: "new-1"}),
        (slice(None, 4), 1, {1: "replacement-0", 2: "new-0", 3: "new-1"}),
        (slice(None), 2, {1: "replacement-0", 2: "replacement-1"}),
        (slice(2, 2), 2, {3: "replacement-0", 4: "replacement-1", 7: "new-0", 8: "new-1"}),
        (slice(4, 2), 2, {5: "replacement-0", 6: "replacement-1", 7: "new-0", 8: "new-1"}),
        (slice(3, 1), 2, {4: "replacement-0", 5: "replacement-1", 7: "new-0", 8: "new-1"}),
        (slice(None, None, 2), 3, {1: "replacement-0", 3: "replacement-1", 5: "replacement-2", 6: "new-1"}),
        (slice(None, None, -2), 3, {2: "replacement-2", 4: "replacement-1", 5: "new-0", 6: "replacement-0"}),
    ],
)
def test_new_entries_assigned_to_a_slice_are_current(history, index, count, expected):
    history[index] = (item(f"replacement-{i}") for i in range(count))
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, {1: "replacement-0", 5: "new-0", 6: "new-1"}),
        (3, {4: "replacement-0", 5: "new-0", 6: "new-1"}),
        (4, {5: "replacement-0", 6: "new-1"}),
        (-1, {5: "new-0", 6: "replacement-0"}),
    ],
)
def test_new_entry_assigned_to_an_index_is_current(history, index, expected):
    history[index] = item("replacement-0")
    assert current_session(history) == expected


def test_new_entry_assigned_into_empty_session_is_current():
    hist = History(item(f"old-{i}") for i in range(4))
    hist.start_session()
    hist[:] = [hist[1], item("new-0")]
    assert current_session(hist) == {2: "new-0"}


def test_self_assignment_copies_membership(history):
    history[:] = history
    assert current_session(history) == {5: "new-0", 6: "new-1"}
    history[1:3] = history
    assert current_session(history) == {6: "new-0", 7: "new-1", 9: "new-0", 10: "new-1"}


def repeat_twice(hist):
    hist *= 2


def extend_with_itself(hist):
    hist += list(hist)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda hist: hist.reverse(), {1: "new-1", 2: "new-0"}),
        (lambda hist: hist.sort(key=lambda entry: entry.raw), {1: "new-0", 2: "new-1"}),
        (lambda hist: hist.sort(key=lambda entry: entry.raw, reverse=True), {5: "new-1", 6: "new-0"}),
        (repeat_twice, {5: "new-0", 6: "new-1", 11: "new-0", 12: "new-1"}),
        (extend_with_itself, {5: "new-0", 6: "new-1", 11: "new-0", 12: "new-1"}),
    ],
    ids=["reverse", "sort", "sort-descending", "repeat", "extend-with-itself"],
)
def test_moved_or_copied_persisted_entries_stay_out_of_session(history, mutate, expected):
    mutate(history)
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("count", "expected"), [(0, {1: "new-2"}), (-1, {1: "new-2"}), (1, {5: "new-0", 6: "new-1", 7: "new-2"})]
)
def test_repetition_then_append_keeps_new_entry_current(history, count, expected):
    history *= count
    history.append(Statement("", raw="new-2"))
    assert current_session(history) == expected


@pytest.mark.parametrize(
    ("indices", "expected"),
    [
        ([3, 1, 4, 5], {3: "new-0", 4: "new-1"}),
        ([4, 1, 5], {1: "new-0", 3: "new-1"}),
        ([1, 3], {}),
        ([0, 0, 4], {3: "new-0"}),
        ([4, 0, 5, 1], {1: "new-0", 3: "new-1"}),
        ([0, 2, 1, 3, 4, 5], {5: "new-0", 6: "new-1"}),
    ],
)
def test_reordering_by_slice_assignment_keeps_membership(history, indices, expected):
    history[:] = [history[index] for index in indices]
    assert current_session(history) == expected


@pytest.mark.parametrize("as_iterator", [False, True])
@pytest.mark.parametrize(
    ("start", "stop", "removed"),
    [
        (0, 6, {1}),
        (0, 6, {0, 2}),
        (0, 6, {4}),
        (0, 6, {5}),
        (0, 6, {0, 4}),
        (1, 6, {1, 3}),
        (2, 6, {2, 4}),
        (3, 5, {3}),
        (0, 5, {1, 4}),
    ],
)
def test_filtering_by_slice_assignment_keeps_membership(history, start, stop, removed, as_iterator):
    original = list(history)
    replacement = [entry for index, entry in enumerate(original) if start <= index < stop and index not in removed]
    kept = [entry for index, entry in enumerate(original) if index not in removed]
    history[start:stop] = iter(replacement) if as_iterator else replacement
    assert all(actual is wanted for actual, wanted in zip(history, kept, strict=True))
    assert current_session(history) == {
        position: entry.raw for position, entry in enumerate(kept, start=1) if entry.raw.startswith("new-")
    }


def test_equal_commands_from_different_sessions_are_separate_entries(history):
    current = item(history[0].raw)
    assert current == history[0]
    assert current is not history[0]
    history[4] = current
    history[:] = history[1:]
    assert history[3] is current
    assert current_session(history) == {4: "old-0", 5: "new-1"}


def test_new_equal_entry_in_slice_assignment_is_current(history):
    new_entry = item(history[0].raw)
    history[:] = [new_entry, history[1], history[4]]
    assert current_session(history) == {1: "old-0", 3: "new-0"}


def test_reappending_persisted_entry_object_keeps_it_persisted(history):
    history.append(history[2])
    history.append(history[2].statement)
    assert current_session(history) == {5: "new-0", 6: "new-1", 8: "old-2"}


@pytest.mark.parametrize(
    "clone",
    [copy.deepcopy, lambda hist: pickle.loads(pickle.dumps(hist))],
    ids=["deepcopy", "pickle"],
)
def test_cloned_history_keeps_persisted_entries(history, clone):
    assert current_session(clone(history)) == {5: "new-0", 6: "new-1"}


@pytest.mark.parametrize("operation", ["delete", "pop", "remove", "slice_step", "slice_length", "slice_iterator"])
def test_failed_mutation_preserves_history_and_membership(history, operation):
    original = list(history)

    def broken_items():
        yield item("replacement-0")
        raise RuntimeError("incomplete replacement")

    error = IndexError if operation in ("delete", "pop") else RuntimeError if operation == "slice_iterator" else ValueError

    def mutate():
        if operation == "delete":
            del history[-99]
        elif operation == "pop":
            history.pop(-99)
        elif operation == "remove":
            history.remove(item("missing-0"))
        elif operation == "slice_step":
            del history[::0]
        elif operation == "slice_length":
            history[::2] = [item("replacement-0")]
        else:
            history[:2] = broken_items()

    with pytest.raises(error):
        mutate()
    assert all(actual is expected for actual, expected in zip(history, original, strict=True))
    assert current_session(history) == {5: "new-0", 6: "new-1"}


def test_mutations_compose_with_truncate_clear_and_append(history):
    history.insert(0, item("inserted-0"))
    history.pop(1)
    history.truncate(4)
    history.append(Statement("", raw="new-2"))
    assert current_session(history) == {3: "new-0", 4: "new-1", 5: "new-2"}
    history.clear()
    history.extend([item("new-3")])
    assert current_session(history) == {1: "new-3"}


@pytest.mark.parametrize(
    ("mutate", "selector"),
    [(lambda hist: hist.reverse(), "5:6"), (repeat_twice, "7:10")],
    ids=["reverse", "repeat"],
)
def test_moved_persisted_commands_still_require_all(base_app, history, monkeypatch, mutate, selector):
    base_app.history = history
    mutate(history)
    replay = mock.Mock(return_value=False)
    monkeypatch.setattr(base_app, "runcmds_plus_hooks", replay)

    _out, err = run_cmd(base_app, f"history --run {selector}")

    assert err == ["Use --all to run or edit commands from previous sessions."]
    replay.assert_not_called()
