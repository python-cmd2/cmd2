"""Tests for the terminal transaction lock and its wait contract.

Two of these are the named regressions from design section 13.2 --
``test_paint_transaction_rejects_blocking_wait`` and
``test_terminal_lock_order_violation_is_detected``. Both are written against sentinels rather
than real blocking primitives, so a guard that fails to fire makes the test *fail* instead of
hanging the suite, and both assert that the sentinel was never entered: raising after the
wait has already begun would be no protection at all.
"""

import queue
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Self

import pytest

from cmd2.terminal_transaction import (
    HigherLevelLock,
    TerminalLock,
    TerminalTransactionViolationError,
    assert_no_terminal_transaction,
    current_transaction,
    guarded_call,
    held_higher_level_locks,
)

from .conftest import ContendedLock


class Sentinel:
    """A stand-in for a blocking primitive that records being entered instead of blocking."""

    def __init__(self) -> None:
        self.entered = False

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        self.entered = True
        return "finished"


class RecordingLock:
    """A lock that records acquisition rather than ever blocking."""

    def __init__(self) -> None:
        self.acquired = 0

    def acquire(self, *args: Any, **kwargs: Any) -> bool:
        self.acquired += 1
        return True

    def release(self) -> None:
        pass

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


def blocking_primitives() -> list[tuple[str, Any]]:
    """Build one sentinel-backed call per prohibited blocking primitive.

    Each entry is the operation name and a zero-argument callable that would enter the
    primitive if the guard let it through.
    """
    event = threading.Event()
    event.set()
    condition = threading.Condition()
    pending: Future[str] = Future()
    pending.set_result("done")
    work: queue.Queue[str] = queue.Queue()
    work.put("item")
    thread = threading.Thread(target=lambda: None)
    thread.start()
    proxy = Sentinel()

    def condition_wait() -> Any:
        with condition:
            return guarded_call("condition wait", condition.wait, 0.01)

    return [
        ("ui future wait", lambda: guarded_call("ui future wait", pending.result, 0.01)),
        ("event wait", lambda: guarded_call("event wait", event.wait, 0.01)),
        ("condition wait", condition_wait),
        ("queue wait", lambda: guarded_call("queue wait", work.get, True, 0.01)),
        ("thread join", lambda: guarded_call("thread join", thread.join, 0.01)),
        ("sleep", lambda: guarded_call("sleep", time.sleep, 0.01)),
        ("proxy drain", lambda: guarded_call("proxy drain", proxy)),
        ("proxy close", lambda: guarded_call("proxy close", proxy)),
    ]


class TestTransactionState:
    def test_no_transaction_is_active_by_default(self) -> None:
        assert current_transaction() is None

    def test_a_transaction_reports_its_kind_generation_and_thread(self) -> None:
        lock = TerminalLock()
        with lock.transaction("paint", generation=7):
            state = current_transaction()
            assert state is not None
            assert state.kind == "paint"
            assert state.generation == 7
            assert state.depth == 1
            assert state.thread_id == threading.get_ident()

    def test_the_transaction_is_gone_after_the_block(self) -> None:
        lock = TerminalLock()
        with lock.transaction("paint"):
            pass
        assert current_transaction() is None

    def test_the_transaction_is_released_when_the_body_raises(self) -> None:
        lock = TerminalLock()
        with pytest.raises(ZeroDivisionError), lock.transaction("paint"):
            raise ZeroDivisionError
        assert current_transaction() is None

    def test_same_thread_nesting_reuses_the_transaction(self) -> None:
        """An emission helper called from inside another one shares one transaction."""
        lock = TerminalLock()
        with lock.transaction("commit", generation=3):
            with lock.transaction("write"):
                state = current_transaction()
                assert state is not None
                assert state.depth == 2
                # The outer transaction keeps its identity; a nested helper does not
                # relabel the transaction it joined.
                assert state.kind == "commit"
                assert state.generation == 3
            outer = current_transaction()
            assert outer is not None
            assert outer.depth == 1

    def test_another_thread_sees_no_transaction_of_its_own(self) -> None:
        """The guard is per-thread: it must not report one thread's transaction to another."""
        lock = TerminalLock()
        seen: list[Any] = []
        with lock.transaction("paint"):
            worker = threading.Thread(target=lambda: seen.append(current_transaction()))
            worker.start()
            worker.join()
        assert seen == [None]


class TestWaitContract:
    @pytest.mark.parametrize("index", range(len(blocking_primitives())))
    def test_paint_transaction_rejects_blocking_wait(self, index: int) -> None:
        """Named test 13.2: every prohibited wait is refused before the primitive is entered."""
        name, invoke = blocking_primitives()[index]
        lock = TerminalLock()
        with lock.transaction("paint"), pytest.raises(TerminalTransactionViolationError, match=name):
            invoke()

    @pytest.mark.parametrize("index", range(len(blocking_primitives())))
    def test_the_primitive_is_never_entered(self, index: int) -> None:
        """Raising after the wait has started would be no protection: prove it never starts."""
        _name, invoke = blocking_primitives()[index]
        entered: list[str] = []
        lock = TerminalLock()

        def watched() -> Any:
            entered.append("yes")
            return invoke()

        with lock.transaction("paint"), pytest.raises(TerminalTransactionViolationError):
            watched()
        # ``watched`` itself ran; what must not have happened is the guarded primitive.
        assert entered == ["yes"]

    def test_the_same_calls_are_allowed_outside_a_transaction(self) -> None:
        """The guard rejects a context, not the operations themselves."""
        for _name, invoke in blocking_primitives():
            invoke()

    def test_bypassing_the_helper_reaches_the_primitive(self) -> None:
        """The guard is what detects this; a sentinel proves the test would fail without it."""
        proxy = Sentinel()
        lock = TerminalLock()
        with lock.transaction("paint"):
            proxy()
        assert proxy.entered is True

    def test_assert_no_terminal_transaction_names_the_operation(self) -> None:
        lock = TerminalLock()
        with lock.transaction("paint"), pytest.raises(TerminalTransactionViolationError, match="draining the stdout proxy"):
            assert_no_terminal_transaction("draining the stdout proxy")

    def test_assert_no_terminal_transaction_passes_when_released(self) -> None:
        assert_no_terminal_transaction("draining the stdout proxy")


class TestLockOrder:
    def test_terminal_lock_order_violation_is_detected(self) -> None:
        """Named test 13.2: both nesting directions are rejected, the correct order is not."""
        underlying = RecordingLock()
        terminal = TerminalLock(lock=underlying)

        # Higher-level lock held, then the terminal lock: refused before the blocking acquire.
        with (
            HigherLevelLock("routing", lock=RecordingLock()),
            pytest.raises(TerminalTransactionViolationError, match="routing"),
            terminal.transaction("paint"),
        ):
            pass
        assert underlying.acquired == 0

        # Terminal lock held, then the higher-level lock: refused the same way.
        routing = RecordingLock()
        with (
            terminal.transaction("paint"),
            pytest.raises(TerminalTransactionViolationError, match="routing"),
            HigherLevelLock("routing", lock=routing),
        ):
            pass
        assert routing.acquired == 0

        # Release then acquire is the supported order and is not obstructed.
        with HigherLevelLock("routing", lock=routing):
            pass
        with terminal.transaction("paint"):
            pass
        assert underlying.acquired == 2
        assert routing.acquired == 1

    def test_a_higher_level_lock_is_released_when_the_body_raises(self) -> None:
        routing = HigherLevelLock("routing", lock=RecordingLock())
        with pytest.raises(ZeroDivisionError), routing:
            raise ZeroDivisionError
        terminal = TerminalLock(lock=RecordingLock())
        with terminal.transaction("paint"):
            pass

    def test_nested_higher_level_locks_are_all_reported(self) -> None:
        terminal = TerminalLock(lock=RecordingLock())
        with (
            HigherLevelLock("lifecycle", lock=RecordingLock()),
            HigherLevelLock("routing", lock=RecordingLock()),
            pytest.raises(TerminalTransactionViolationError) as info,
            terminal.transaction("paint"),
        ):
            pass
        assert "lifecycle" in str(info.value)
        assert "routing" in str(info.value)

    def test_a_higher_level_lock_may_be_taken_after_the_transaction_ends(self) -> None:
        terminal = TerminalLock(lock=RecordingLock())
        routing = RecordingLock()
        with terminal.transaction("paint"):
            pass
        with HigherLevelLock("routing", lock=routing):
            pass
        assert routing.acquired == 1

    def test_another_thread_may_hold_a_higher_level_lock(self) -> None:
        """Lock order is a per-thread rule; another thread's routing lock is not our problem."""
        terminal = TerminalLock(lock=RecordingLock())
        started = threading.Event()
        finished = threading.Event()

        def worker() -> None:
            with HigherLevelLock("routing", lock=RecordingLock()):
                started.set()
                finished.wait(timeout=5)

        thread = threading.Thread(target=worker)
        thread.start()
        started.wait(timeout=5)
        try:
            with terminal.transaction("paint"):
                pass
        finally:
            finished.set()
            thread.join(timeout=5)


class TestSerialization:
    def test_two_threads_never_hold_the_terminal_at_once(self) -> None:
        """A contender must wait until the owning transaction finishes."""
        observed = ContendedLock()
        terminal = TerminalLock(lock=observed)
        order = []

        def emit() -> None:
            with terminal.transaction("paint"):
                order.append("contender")

        with ThreadPoolExecutor(max_workers=1) as pool:
            with terminal.transaction("owner"):
                pending = pool.submit(emit)
                assert observed.contended.wait(5), "contender bypassed the terminal lock"
                assert order == []
                assert not pending.done()
                order.append("owner")
            pending.result(timeout=5)
        assert order == ["owner", "contender"]


class TestDiagnostics:
    def test_the_guard_reports_held_locks_outermost_first(self) -> None:
        assert held_higher_level_locks() == ()
        with HigherLevelLock("lifecycle", lock=RecordingLock()), HigherLevelLock("routing", lock=RecordingLock()):
            assert held_higher_level_locks() == ("lifecycle", "routing")
        assert held_higher_level_locks() == ()

    def test_a_higher_level_lock_reports_what_it_protects(self) -> None:
        assert HigherLevelLock("routing", lock=RecordingLock()).name == "routing"

    def test_the_terminal_lock_reports_whether_this_thread_holds_it(self) -> None:
        terminal = TerminalLock(lock=RecordingLock())
        assert terminal.active is False
        with terminal.transaction("paint"):
            assert terminal.active is True
        assert terminal.active is False
