"""Tests for writing command output to a reserved terminal.

The rule this module exists to keep is an ordering one: a command's output and the toolbar's
paint reach the terminal one after the other, never interleaved, and the bridge learns that
output happened *inside* the same transaction that emitted it. Told afterwards, it would be
told about a terminal that had already changed again.
"""

import io
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Self

import pytest

from cmd2.command_toolbar import ToolbarStream
from cmd2.managed_output import SerializedTerminalWriter
from cmd2.terminal_transaction import TerminalLock, current_transaction

from .conftest import ContendedLock


class RecordingBridge:
    """A stand-in for the bridge, recording when it was told and by whom."""

    def __init__(self) -> None:
        self.notes: list[Any] = []
        self.anchors: list[int | None] = []

    def note_managed_write(self, prompt_anchor: int | None = None, *, data: str | None = None) -> None:
        self.notes.append(current_transaction())
        self.anchors.append(prompt_anchor)


class RecordingStream(io.StringIO):
    """A terminal stream that records the transaction each write and flush ran in."""

    def __init__(self) -> None:
        super().__init__()
        self.transactions: list[Any] = []
        self.flushes = 0

    def write(self, text: str) -> int:
        self.transactions.append(current_transaction())
        return super().write(text)

    def flush(self) -> None:
        self.flushes += 1
        super().flush()


def make(bridge: RecordingBridge | None = None) -> tuple[SerializedTerminalWriter, RecordingStream, TerminalLock]:
    """Build a writer over a recording stream."""
    stream = RecordingStream()
    lock = TerminalLock()
    return SerializedTerminalWriter(stream, lock, bridge), stream, lock


class TestWriting:
    def test_output_reaches_the_stream(self) -> None:
        writer, stream, _lock = make()
        writer.write("hello\n")
        assert stream.getvalue() == "hello\n"

    def test_the_count_of_characters_written_is_returned(self) -> None:
        writer, _stream, _lock = make()
        assert writer.write("hello") == 5

    def test_every_write_is_flushed(self) -> None:
        """The toolbar paints after this; unflushed output would appear after the paint."""
        writer, stream, _lock = make()
        writer.write("hello")
        assert stream.flushes >= 1

    def test_the_write_happens_inside_a_terminal_transaction(self) -> None:
        writer, stream, _lock = make()
        writer.write("hello")
        assert stream.transactions
        assert all(state is not None for state in stream.transactions)

    def test_an_empty_write_still_takes_the_terminal(self) -> None:
        """Ordering is about the sequence of transactions, not about how much was written."""
        writer, stream, _lock = make()
        assert writer.write("") == 0
        assert stream.flushes >= 1

    def test_flushing_takes_the_terminal(self) -> None:
        writer, stream, _lock = make()
        writer.flush()
        assert stream.flushes >= 1

    def test_the_stream_is_reachable(self) -> None:
        writer, stream, _lock = make()
        assert writer.stream is stream

    def test_file_attributes_come_from_the_stream(self) -> None:
        """Callers ask streams whether they are a terminal, and what their encoding is."""
        writer, stream, _lock = make()
        assert writer.readable() == stream.readable()


class TestInvalidationContract:
    def test_the_bridge_is_told_inside_the_emitting_transaction(self) -> None:
        """Told afterwards, it would be told about a terminal that has changed again."""
        bridge = RecordingBridge()
        writer, _stream, _lock = make(bridge)
        writer.write("hello\n")
        assert len(bridge.notes) == 1
        assert bridge.notes[0] is not None

    def test_the_prompt_origin_is_not_claimed(self) -> None:
        """The output moved the cursor and may have scrolled; where it ended is not known."""
        bridge = RecordingBridge()
        writer, _stream, _lock = make(bridge)
        writer.write("hello\n")
        assert bridge.anchors == [None]

    def test_a_flush_alone_does_not_claim_output_happened(self) -> None:
        bridge = RecordingBridge()
        writer, _stream, _lock = make(bridge)
        writer.flush()
        assert bridge.notes == []

    def test_a_writer_without_a_bridge_still_writes(self) -> None:
        """Output outside a reserved session has nothing to invalidate."""
        writer, stream, _lock = make()
        writer.write("hello")
        assert stream.getvalue() == "hello"

    def test_the_bridge_can_be_attached_later(self) -> None:
        """The streams outlive any one reservation; the bridge does not."""
        writer, _stream, _lock = make()
        bridge = RecordingBridge()
        writer.bridge = bridge
        writer.write("hello")
        assert len(bridge.notes) == 1


class TestOrdering:
    def test_a_write_and_a_paint_do_not_interleave(self) -> None:
        """A managed write cannot reach the stream while a paint owns the terminal."""
        observed = ContendedLock()
        lock = TerminalLock(lock=observed)
        stream = RecordingStream()
        writer = SerializedTerminalWriter(stream, lock, None)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with lock.transaction("paint"):
                pending = pool.submit(writer.write, "output\n")
                assert observed.contended.wait(5), "write bypassed the paint's lock"
                assert stream.getvalue() == ""
                assert not pending.done()
                stream.write("paint\n")
            assert pending.result(timeout=5) == len("output\n")
        assert stream.getvalue() == "paint\noutput\n"

    def test_writes_from_two_threads_are_not_torn(self) -> None:
        writer, stream, _lock = make()

        def emit(text: str) -> None:
            for _ in range(20):
                writer.write(text)

        threads = [threading.Thread(target=emit, args=(text,)) for text in ("aaaa", "bbbb")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        written = stream.getvalue()
        assert len(written) == 160
        assert written.count("aaaa") == 20
        assert written.count("bbbb") == 20


class TestToolbarStreamRouting:
    """The stream a command writes to has three possible destinations, in priority order."""

    def make_stream(self) -> tuple[ToolbarStream, RecordingStream]:
        """Build a toolbar stream over a recording terminal stream."""
        original = RecordingStream()
        return ToolbarStream(original, threading.RLock()), original

    def test_output_goes_to_the_terminal_when_nothing_is_installed(self) -> None:
        stream, original = self.make_stream()
        stream.write("hello")
        assert original.getvalue() == "hello"

    def test_the_serializer_takes_priority_over_the_proxy(self) -> None:
        """In reserved mode the proxy's erase-and-redraw is exactly what must not happen."""
        stream, original = self.make_stream()
        proxy = RecordingStream()
        stream.proxy = proxy  # type: ignore[assignment]
        stream.serializer = SerializedTerminalWriter(original, TerminalLock())

        stream.write("hello")
        assert original.getvalue() == "hello"
        assert proxy.getvalue() == ""

    def test_the_proxy_is_used_when_no_serializer_is_installed(self) -> None:
        stream, original = self.make_stream()
        proxy = RecordingStream()
        stream.proxy = proxy  # type: ignore[assignment]

        stream.write("hello")
        assert proxy.getvalue() == "hello"
        assert original.getvalue() == ""

    def test_the_routing_lock_is_released_before_the_terminal_is_taken(self) -> None:
        """Lock order: a routing lock held into the terminal transaction is the deadlock."""
        original = RecordingStream()
        routing = threading.RLock()
        stream = ToolbarStream(original, routing)
        stream.serializer = SerializedTerminalWriter(original, TerminalLock())

        held: list[bool] = []
        real_write = original.write

        def watched(text: str) -> int:
            # Asked from another thread: the routing lock is re-entrant, so the writing
            # thread could always take it again regardless of whether it still holds it.
            def probe() -> None:
                acquired = routing.acquire(blocking=False)
                held.append(not acquired)
                if acquired:
                    routing.release()

            prober = threading.Thread(target=probe)
            prober.start()
            prober.join(timeout=5)
            return real_write(text)

        original.write = watched  # type: ignore[method-assign]
        worker = threading.Thread(target=lambda: stream.write("hello"))
        worker.start()
        worker.join(timeout=5)
        assert held == [False]

    def test_flushing_follows_the_same_priority(self) -> None:
        stream, original = self.make_stream()
        stream.serializer = SerializedTerminalWriter(original, TerminalLock())
        stream.flush()
        assert original.flushes >= 1


class FailingStream(RecordingStream):
    """A terminal that fails a chosen operation, having possibly emitted something first."""

    def __init__(self, fail_write: bool = False, fail_flush: bool = False) -> None:
        super().__init__()
        self._fail_write = fail_write
        self._fail_flush = fail_flush

    def write(self, text: str) -> int:
        if self._fail_write:
            super().write(text[:3])
            raise OSError("terminal went away")
        return super().write(text)

    def flush(self) -> None:
        super().flush()
        if self._fail_flush:
            raise OSError("terminal went away")


class TestFailedWrites:
    def test_a_failed_write_still_invalidates(self) -> None:
        """Part of the output may be on the screen; the bridge cannot be left believing not."""
        bridge = RecordingBridge()
        writer = SerializedTerminalWriter(FailingStream(fail_write=True), TerminalLock(), bridge)
        with pytest.raises(OSError, match="terminal went away"):
            writer.write("hello")
        assert len(bridge.notes) == 1
        assert bridge.notes[0] is not None

    def test_a_failed_flush_still_invalidates(self) -> None:
        bridge = RecordingBridge()
        writer = SerializedTerminalWriter(FailingStream(fail_flush=True), TerminalLock(), bridge)
        with pytest.raises(OSError, match="terminal went away"):
            writer.write("hello")
        assert len(bridge.notes) == 1

    def test_the_original_failure_is_what_reaches_the_caller(self) -> None:
        bridge = RecordingBridge()
        writer = SerializedTerminalWriter(FailingStream(fail_write=True), TerminalLock(), bridge)
        with pytest.raises(OSError, match="terminal went away"):
            writer.write("hello")

    def test_the_invalidation_happens_inside_the_transaction(self) -> None:
        """Told after the lock is given up, it would describe a terminal already changed."""
        bridge = RecordingBridge()
        writer = SerializedTerminalWriter(FailingStream(fail_flush=True), TerminalLock(), bridge)
        with pytest.raises(OSError, match="terminal went away"):
            writer.write("hello")
        assert bridge.notes[0] is not None


class CountingLock:
    """A routing lock that counts how many times it was taken."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.acquisitions = 0

    def __enter__(self) -> Self:
        self._lock.acquire()
        self.acquisitions += 1
        return self

    def __exit__(self, *args: object) -> None:
        self._lock.release()

    def acquire(self, *args: Any, **kwargs: Any) -> bool:
        self.acquisitions += 1
        return self._lock.acquire(*args, **kwargs)

    def release(self) -> None:
        self._lock.release()


class TestRoutingIsDecidedOnce:
    """One acquisition per write, or the destination can change between the two."""

    def test_a_legacy_write_takes_the_routing_lock_once(self) -> None:
        lock = CountingLock()
        stream = ToolbarStream(RecordingStream(), lock)  # type: ignore[arg-type]
        stream.write("hello")
        assert lock.acquisitions == 1

    def test_a_serialized_write_takes_the_routing_lock_once(self) -> None:
        lock = CountingLock()
        original = RecordingStream()
        stream = ToolbarStream(original, lock)  # type: ignore[arg-type]
        stream.serializer = SerializedTerminalWriter(original, TerminalLock())
        stream.write("hello")
        assert lock.acquisitions == 1

    def test_a_flush_takes_the_routing_lock_once(self) -> None:
        lock = CountingLock()
        stream = ToolbarStream(RecordingStream(), lock)  # type: ignore[arg-type]
        stream.flush()
        assert lock.acquisitions == 1

    def test_a_serializer_installed_after_the_decision_is_not_missed_by_the_next_write(self) -> None:
        """A write in flight keeps its destination; the one after it sees the new one."""
        original = RecordingStream()
        stream = ToolbarStream(original, threading.RLock())
        stream.write("before")
        stream.serializer = SerializedTerminalWriter(original, TerminalLock())
        stream.write("after")
        assert original.transactions[0] is None
        assert original.transactions[-1] is not None
