"""Session selection survives structural changes to the public history list."""

import pytest

from cmd2.history import History, HistoryItem
from cmd2.parsing import Statement


def item(raw):
    return HistoryItem(Statement("", raw=raw))


@pytest.fixture
def history():
    hist = History(item(f"old-{i}") for i in range(4))
    hist.start_session()
    hist.extend(item(f"new-{i}") for i in range(2))
    return hist


def assert_session(hist, boundary, expected):
    assert hist.session_start_index == boundary
    assert [entry.raw for entry in hist.span(":").values()] == expected
    assert [entry.raw for entry in hist.str_search("-").values()] == expected
    assert [entry.raw for entry in hist.regex_search(".*").values()] == expected
    assert list(hist.span(":")) == list(range(boundary + 1, len(hist) + 1))


@pytest.mark.parametrize(
    ("index", "boundary", "expected"),
    [
        (0, 3, ["new-0", "new-1"]),
        (-6, 3, ["new-0", "new-1"]),
        (-1, 4, ["new-0"]),
        (slice(None, 2), 2, ["new-0", "new-1"]),
        (slice(2, 5), 2, ["new-1"]),
        (slice(None, None, 2), 2, ["new-1"]),
        (slice(None, None, -2), 2, ["new-0"]),
        (slice(5, 1, -2), 3, ["new-0"]),
        (slice(None), 0, []),
        (slice(1, 1), 4, ["new-0", "new-1"]),
    ],
)
def test_delete_tracks_session(history, index, boundary, expected):
    del history[index]
    assert_session(history, boundary, expected)


@pytest.mark.parametrize(
    ("index", "removed", "boundary", "expected"),
    [
        (0, "old-0", 3, ["new-0", "new-1"]),
        (-3, "old-3", 3, ["new-0", "new-1"]),
        (-1, "new-1", 4, ["new-0"]),
    ],
)
def test_pop_tracks_session(history, index, removed, boundary, expected):
    assert history.pop(index).raw == removed
    assert_session(history, boundary, expected)


@pytest.mark.parametrize(("raw", "boundary", "expected"), [("old-1", 3, ["new-0", "new-1"]), ("new-1", 4, ["new-0"])])
def test_remove_tracks_session(history, raw, boundary, expected):
    assert history.remove(item(raw)) is None
    assert_session(history, boundary, expected)


@pytest.mark.parametrize(
    ("index", "boundary", "expected"),
    [
        (0, 5, ["new-0", "new-1"]),
        (3, 5, ["new-0", "new-1"]),
        (-3, 5, ["new-0", "new-1"]),
        (-99, 5, ["new-0", "new-1"]),
        (4, 4, ["inserted-0", "new-0", "new-1"]),
        (99, 4, ["new-0", "new-1", "inserted-0"]),
        (-1, 4, ["new-0", "inserted-0", "new-1"]),
    ],
)
def test_insert_tracks_session(history, index, boundary, expected):
    history.insert(index, item("inserted-0"))
    assert_session(history, boundary, expected)


@pytest.mark.parametrize(
    ("index", "count", "boundary", "expected"),
    [
        (slice(0, 1), 2, 5, ["new-0", "new-1"]),
        (slice(1, 3), 0, 2, ["new-0", "new-1"]),
        (slice(2, 5), 2, 4, ["new-1"]),
        (slice(2, 5), 4, 4, ["replacement-2", "replacement-3", "new-1"]),
        (slice(4, 5), 2, 4, ["replacement-0", "replacement-1", "new-1"]),
        (slice(None, 4), 1, 1, ["new-0", "new-1"]),
        (slice(None), 2, 2, []),
        (slice(2, 2), 2, 6, ["new-0", "new-1"]),
        (slice(4, 2), 2, 4, ["replacement-0", "replacement-1", "new-0", "new-1"]),
        (slice(3, 1), 2, 6, ["new-0", "new-1"]),
        (slice(None, None, 2), 3, 4, ["replacement-2", "new-1"]),
        (slice(None, None, -2), 3, 4, ["new-0", "replacement-0"]),
    ],
)
def test_slice_assignment_tracks_session(history, index, count, boundary, expected):
    history[index] = (item(f"replacement-{i}") for i in range(count))
    assert_session(history, boundary, expected)


def test_self_assignment_preserves_session(history):
    history[:] = history
    assert_session(history, 4, ["new-0", "new-1"])
    history[1:3] = history
    assert_session(history, 8, ["new-0", "new-1"])


@pytest.mark.parametrize("index", [0, 3, 4, -1])
def test_index_assignment_preserves_session(history, index):
    history[index] = item("replacement-0")
    assert_session(history, 4, [entry.raw for entry in history[4:]])


@pytest.mark.parametrize("count", [0, -1, 1, 2])
def test_repetition_preserves_session_boundary(history, count):
    history *= count
    boundary = 0 if count <= 0 else 4
    assert_session(history, boundary, [entry.raw for entry in history[boundary:]])


@pytest.mark.parametrize("operation", ["delete", "pop", "remove", "slice_step", "slice_length", "slice_iterator"])
def test_failed_mutation_preserves_history_and_boundary(history, operation):
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
    assert history == original
    assert_session(history, 4, ["new-0", "new-1"])


def test_mutations_compose_with_truncate_and_append(history):
    history.insert(0, item("inserted-0"))
    history.pop(1)
    history.truncate(4)
    history.append(Statement("", raw="new-2"))
    assert_session(history, 2, ["new-0", "new-1", "new-2"])
    history.clear()
    history.extend([item("new-3")])
    assert_session(history, 0, ["new-3"])


def test_remove_retains_native_list_dispatch(history):
    class CustomHistory(History):
        def index(self, *_args):
            raise AssertionError("remove must not dispatch to an overridden index")

        def pop(self, *_args):
            raise AssertionError("remove must not dispatch to an overridden pop")

    custom = CustomHistory(history)
    custom.session_start_index = history.session_start_index
    custom.remove(item("old-1"))
    assert_session(custom, 3, ["new-0", "new-1"])
