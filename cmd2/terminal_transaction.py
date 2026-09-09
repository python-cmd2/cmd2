"""The terminal transaction lock and the wait contract that keeps it deadlock-free.

Every byte cmd2 sends to the terminal -- a renderer frame replayed by the bridge, a toolbar
paint, a managed write, a margin change -- is emitted inside one *terminal transaction*.
Serializing individual output methods is not enough: a paint that lands between a renderer's
cursor move and its text write puts the text somewhere other than where the renderer meant
it, and both calls were individually locked.

:class:`TerminalLock` is ``L_terminal``: the last lock in the output path. The rules it
enforces are the ones that make "last" true.

**Nothing higher-level may be held while taking it.** Stream routing locks, ownership and
lifecycle locks, queue locks -- all are released first. :class:`HigherLevelLock` records that
a thread holds one, so taking the terminal lock underneath it is refused *before* a real
blocking acquire rather than discovered as a deadlock.

**Nothing that can wait may run while holding it.** No application callback, no proxy drain,
no future or event or queue wait, no join, no sleep. :func:`guarded_call` refuses those
synchronously, before the primitive is entered; a violation that fires after the wait has
begun protects nothing.

The unavoidable exception is leaf I/O. ``write()``, ``flush()`` and native console calls can
block on the operating system, and they belong inside the boundary precisely because they are
the emission. Isolating them behind the physical backend keeps them from calling back into
cmd2; it does not make them non-blocking, and this module claims no such thing.

The guard is per-thread and always on. Its cost is a thread-local attribute read, which is
cheaper than the class of bug it catches is to diagnose from a hung terminal.
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Protocol, Self, TypeVar

_T = TypeVar("_T")


class TerminalTransactionViolationError(RuntimeError):
    """Raised when the lock or wait contract would be broken.

    This is deliberately an error rather than a warning. The operations it guards deadlock or
    corrupt the display when they are allowed through, and both failures are far harder to
    attribute after the fact than an exception at the call site.

    The design calls this ``TerminalTransactionViolation``; the ``Error`` suffix is the
    repository's naming rule for exceptions.
    """


class _Lock(Protocol):
    """The subset of a lock this module uses, so tests can supply a non-blocking double."""

    def acquire(self, *args: Any, **kwargs: Any) -> bool:
        """Take the lock."""
        ...  # pragma: no cover

    def release(self) -> None:
        """Give the lock back."""
        ...  # pragma: no cover


@dataclass(frozen=True)
class TransactionState:
    """What the debug guard records about the transaction a thread is inside."""

    #: What the transaction is for, for diagnostics: ``"paint"``, ``"commit"``, and so on.
    kind: str

    #: How many nested emission helpers are sharing this transaction.
    depth: int

    #: The thread that owns it. A transaction is never visible to another thread.
    thread_id: int

    #: The geometry generation the transaction validated against, where it has one.
    generation: int | None = None


class _GuardState(threading.local):
    """Per-thread record of the transaction and the higher-level locks this thread holds."""

    def __init__(self) -> None:
        self.transaction: TransactionState | None = None
        self.held_locks: list[str] = []


_state = _GuardState()


def current_transaction() -> TransactionState | None:
    """Report the terminal transaction this thread is inside, if any.

    :return: the active transaction state, or ``None``
    """
    return _state.transaction


def held_higher_level_locks() -> tuple[str, ...]:
    """Report the higher-level locks this thread holds, outermost first.

    :return: the names of the held locks
    """
    return tuple(_state.held_locks)


def assert_no_terminal_transaction(operation: str) -> None:
    """Refuse an operation that must not run inside a terminal transaction.

    Call this *before* every blocking helper, callback dispatch, proxy drain or close, and
    join that cmd2 owns -- not after, and not inside the primitive.

    :param operation: what was about to happen, named for the error message
    :raises TerminalTransactionViolationError: if this thread is inside a transaction
    """
    active = _state.transaction
    if active is not None:
        raise TerminalTransactionViolationError(
            f"{operation} is not allowed inside the {active.kind} terminal transaction "
            f"(depth {active.depth}); release the terminal lock first"
        )


def guarded_call(operation: str, func: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Run a call that may block, refusing it inside a terminal transaction.

    :param operation: what the call is, named for the error message
    :param func: the callable to run
    :param args: positional arguments for ``func``
    :param kwargs: keyword arguments for ``func``
    :return: whatever ``func`` returns
    :raises TerminalTransactionViolationError: if this thread is inside a transaction
    """
    assert_no_terminal_transaction(operation)
    return func(*args, **kwargs)


class HigherLevelLock:
    """A lock that ranks above ``L_terminal`` and must be released before it is taken.

    Stream routing, ownership and lifecycle, application state and work queues all live here.
    Holding one while acquiring the terminal lock is the deadlock: the thread holding the
    terminal lock cannot finish emitting until a worker gets the routing lock back, and the
    worker cannot until the emitter gives it up.
    """

    def __init__(self, name: str, lock: _Lock | None = None) -> None:
        """Wrap a lock under a name that appears in violation messages.

        :param name: what this lock protects, for diagnostics
        :param lock: the lock to wrap; a fresh :class:`threading.RLock` by default
        """
        self._name = name
        self._lock: _Lock = lock if lock is not None else threading.RLock()

    @property
    def name(self) -> str:
        """What this lock protects."""
        return self._name

    def __enter__(self) -> Self:
        """Take the lock, refusing to do so from inside a terminal transaction.

        :return: this lock
        :raises TerminalTransactionViolationError: if this thread is inside a transaction
        """
        assert_no_terminal_transaction(f"acquiring the {self._name} lock")
        self._lock.acquire()
        _state.held_locks.append(self._name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Give the lock back, including when the body raised."""
        _state.held_locks.pop()
        self._lock.release()


class TerminalLock:
    """``L_terminal``: the final lock in the output path.

    Re-entrant on one thread so that an emission helper may call another, but a nested
    transaction joins the outer one rather than starting its own -- the outer transaction's
    kind and generation are what a violation message should name, because the outer one is
    what validated against the terminal.
    """

    def __init__(self, lock: _Lock | None = None) -> None:
        """Build a terminal lock.

        :param lock: the lock to serialize on; a fresh :class:`threading.RLock` by default
        """
        self._lock: _Lock = lock if lock is not None else threading.RLock()

    @property
    def active(self) -> bool:
        """Whether this thread is currently inside a terminal transaction."""
        return _state.transaction is not None

    @contextmanager
    def transaction(self, kind: str, generation: int | None = None) -> Iterator[TransactionState]:
        """Hold the terminal for the duration of one transaction.

        :param kind: what the transaction is for, for diagnostics
        :param generation: the geometry generation it was validated against, if any
        :return: a context manager yielding the transaction state
        :raises TerminalTransactionViolationError: if this thread holds a higher-level lock
        """
        active = _state.transaction
        if active is not None:
            nested = TransactionState(
                kind=active.kind,
                depth=active.depth + 1,
                thread_id=active.thread_id,
                generation=active.generation,
            )
            _state.transaction = nested
            try:
                yield nested
            finally:
                _state.transaction = active
            return

        if _state.held_locks:
            held = ", ".join(_state.held_locks)
            raise TerminalTransactionViolationError(
                f"cannot start the {kind} terminal transaction while holding {held}; "
                f"higher-level locks are released before the terminal lock is taken"
            )

        self._lock.acquire()
        state = TransactionState(kind=kind, depth=1, thread_id=threading.get_ident(), generation=generation)
        _state.transaction = state
        try:
            yield state
        finally:
            _state.transaction = None
            self._lock.release()
