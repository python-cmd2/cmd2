"""Write command output to a reserved terminal, in order and on the record.

In legacy rendering, output written while a command runs goes through prompt-toolkit's stdout
proxy, which erases the toolbar, prints, and draws it again. That erase-and-redraw is the
flicker the reserved row exists to remove: with rows withheld from scrolling, output can go
straight to the terminal and the toolbar simply stays where it is.

Straight to the terminal, but not at any moment. Two rules make that safe.

**One writer at a time.** The write and its flush happen inside the terminal transaction, the
same one the painter and the renderer take, so a command's output and a toolbar paint reach
the terminal one after the other rather than interleaved.

**The bridge learns inside that transaction.** Output moves the cursor and may scroll the
screen, which invalidates what the renderer believes about the prompt. Telling the bridge
after the lock is released would tell it about a terminal that may have changed again in
between; telling it inside is what makes "the terminal changed" and "the change was recorded"
one event.

No prompt origin is claimed. Where the cursor ended up after arbitrary output -- wrapped
lines, embedded control sequences, a resize mid-write -- is not something this layer knows, and
a guess would put the next prompt over committed output. Recovery asks the terminal instead.
"""

from typing import TYPE_CHECKING, Any

from .terminal_transaction import TerminalLock

if TYPE_CHECKING:  # pragma: no cover
    from typing import TextIO


class SerializedTerminalWriter:
    """A stream that writes to the terminal under the terminal transaction lock."""

    def __init__(self, stream: "TextIO", lock: TerminalLock, bridge: Any = None) -> None:
        """Wrap the terminal's own stream.

        :param stream: the *original* terminal stream. Never a proxy over it: a physical
            writer that routed back into a proxy would queue its own output behind itself.
        :param lock: the terminal transaction lock every cmd2-controlled writer shares
        :param bridge: the renderer bridge to inform of managed output, if one is active
        """
        self._stream = stream
        self._lock = lock
        self.bridge = bridge

    @property
    def stream(self) -> "TextIO":
        """The terminal stream being written to."""
        return self._stream

    def write(self, data: str) -> int:
        """Write command output to the terminal, then record that it happened.

        :param data: the text to write
        :return: the number of characters written
        """
        with self._lock.transaction("managed write"):
            try:
                written = self._stream.write(data)
                # Flushed before the lock is given up. Left buffered, this output would reach
                # the terminal after whatever paints next, which is the ordering the
                # transaction is supposed to establish.
                self._stream.flush()
            finally:
                # Recorded whether or not the write succeeded, and still inside the
                # transaction. A write that raised may have emitted part of its text and may
                # have scrolled the screen doing it -- a stream cannot say which -- so the
                # bridge must not be left believing the terminal is as it was. Invalidating
                # after output that never arrived costs a repaint; not invalidating after
                # output that did costs a prompt drawn over it.
                if self.bridge is not None:
                    self.bridge.note_managed_write()
        return written

    def flush(self) -> None:
        """Flush the terminal stream.

        Nothing is recorded: a flush moves no cursor and scrolls nothing, so it invalidates
        nothing either. The write that produced the buffered output already said so.
        """
        with self._lock.transaction("managed flush"):
            self._stream.flush()

    def __getattr__(self, name: str) -> Any:
        """Delegate file attributes to the terminal stream.

        :param name: the attribute to fetch
        :return: the underlying stream's attribute
        """
        return getattr(self._stream, name)
