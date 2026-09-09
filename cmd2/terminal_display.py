"""Terminal ownership, geometry generations and the bottom-row reservation.

The reservation is a property of the *physical* terminal, so everything here reads size
from the backend prompt-toolkit originally selected and never from the virtual adapter
layered over it. Sizing the region from a view that has already had the reservation
subtracted removes it twice, and the toolbar is then painted over by the last usable row.

Three responsibilities live here:

:class:`Geometry`
    One immutable snapshot per generation. ``usable_rows`` is derived rather than stored so
    that no caller can pass in a height with the reservation already removed.

:class:`PhysicalTerminal`
    The unwrapped source of true size, the writer of margin sequences, and the place where
    backend capability is decided. Capability is decided by backend identity, never by shell
    name, ``TERM``, or ``isinstance(output, Output)`` -- ``Windows10_Output`` is a
    *registered virtual* subclass of ``Output`` and satisfies that check without inheriting
    the interface, and legacy ``Win32Output`` satisfies it too while having no VT scroll
    margins at all.

:class:`TerminalDisplay`
    Acquisition, nested leases, idempotent release and restoration of the original binding.

The reservation is never installed below :data:`~cmd2.scroll_region.MIN_USABLE_ROWS` usable
rows. That floor is total rather than degraded: a terminal silently ignores a degenerate
region and then scrolls straight through the reserved row, destroying the toolbar. Below the
floor the display releases and reports full geometry, and it reacquires when the terminal
grows back.
"""

from contextlib import suppress
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from prompt_toolkit.data_structures import Size

from .scroll_region import (
    MIN_USABLE_ROWS,
    cursor_restore_sequence,
    cursor_save_sequence,
    reset_scroll_region_sequence,
    scroll_region_sequence,
)

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.output import Output

#: Backends whose reserved-row support is qualified, by fully qualified class name. Membership
#: is deliberately explicit: an unrecognized backend gets compatibility behavior rather than
#: raw DECSTBM, because a wrong guess corrupts the user's screen rather than merely rendering
#: poorly. See design §11.
_QUALIFIED_BACKENDS = frozenset(
    {
        "prompt_toolkit.output.vt100.Vt100_Output",
        "prompt_toolkit.output.windows10.Windows10_Output",
    }
)

#: Backends known *not* to support the reservation, with the reason reported by diagnostics.
_DISQUALIFIED_BACKENDS = {
    "prompt_toolkit.output.win32.Win32Output": "legacy Win32 console has no VT scroll margins",
    "prompt_toolkit.output.plain_text.PlainTextOutput": "plain-text output emits no control sequences",
    "prompt_toolkit.output.DummyOutput": "dummy output is not a terminal",
    "prompt_toolkit.output.base.DummyOutput": "dummy output is not a terminal",
}


def _class_name(obj: object) -> str:
    """Build the fully qualified class name of an object.

    :param obj: the object to name
    :return: ``module.QualName`` for the object's type
    """
    cls = type(obj)
    return f"{cls.__module__}.{cls.__qualname__}"


@dataclass(frozen=True)
class Geometry:
    """An immutable snapshot of the terminal as one generation saw it.

    ``usable_rows`` is a derived property rather than a field. Storing it would let a caller
    supply a height that already had the reservation removed, which subtracts it twice: at 24
    physical rows with one reserved row every component must see 23 usable rows, never 22.
    """

    #: Monotonic generation counter; a new snapshot is a new generation, never a mutation.
    generation: int

    #: True viewport height, read from the unwrapped backend.
    physical_rows: int

    #: Terminal width. Toolbar height is measured against this, so a width change is a new
    #: generation even when the height is unchanged.
    columns: int

    #: Rows withheld from the scroll region at the bottom of the screen.
    reserved_rows: int

    #: Identity of the screen buffer and viewport origin. A viewport-origin change invalidates
    #: the generation even when width and height are identical, because absolute row numbers
    #: then address different cells. ``None`` where the backend exposes no such notion.
    buffer_id: object = None

    @property
    def usable_rows(self) -> int:
        """Rows available to the application, excluding the reservation."""
        return self.physical_rows - self.reserved_rows

    @property
    def is_eligible(self) -> bool:
        """Whether this geometry leaves enough room to install a reservation at all."""
        return self.reserved_rows >= 1 and self.usable_rows >= MIN_USABLE_ROWS

    @property
    def virtual_size(self) -> Size:
        """The size the application is shown while the reservation is installed."""
        return Size(rows=self.usable_rows, columns=self.columns)

    @property
    def physical_size(self) -> Size:
        """The true size of the terminal, reservation included."""
        return Size(rows=self.physical_rows, columns=self.columns)


class PhysicalTerminal:
    """The unwrapped backend: true geometry, margin operations and capability selection.

    This never consults the virtual adapter. Its whole purpose is to be the one place that
    still sees the terminal as it really is.
    """

    def __init__(self, output: "Output") -> None:
        """Bind to the backend prompt-toolkit selected.

        :param output: the original, unwrapped output object
        :raises TypeError: if handed an adapter rather than a real backend, which would make
            every size reading a reservation short
        """
        if getattr(output, "is_reserved_adapter", False):
            raise TypeError("PhysicalTerminal must wrap the original backend, not the reserved adapter")
        self._output = output

    @property
    def output(self) -> "Output":
        """The original backend object."""
        return self._output

    @property
    def backend_name(self) -> str:
        """Fully qualified class name of the selected backend."""
        return _class_name(self._output)

    def capability(self) -> tuple[bool, str]:
        """Decide whether this backend supports a reserved row, and say why.

        :return: whether the reservation is supported, and a reason suitable for diagnostics
        """
        name = self.backend_name
        if name in _DISQUALIFIED_BACKENDS:
            return False, _DISQUALIFIED_BACKENDS[name]
        if name in _QUALIFIED_BACKENDS:
            return True, "qualified backend"
        return False, f"{name} is not a qualified backend; using compatibility rendering"

    @property
    def supports_reservation(self) -> bool:
        """Whether this backend is qualified for the reservation."""
        return self.capability()[0]

    def physical_size(self) -> Size:
        """Read the true viewport size from the backend.

        On Windows this is served natively by the outer output object; its inner VT output
        carries a zero-size stub and must never be asked.

        :return: the true terminal size
        """
        return self._output.get_size()

    def buffer_id(self) -> object:
        """Identify the screen buffer and viewport origin, where the backend exposes them.

        :return: an opaque identity comparable across generations, or ``None``
        """
        info_getter = getattr(self._output, "get_win32_screen_buffer_info", None)
        if info_getter is None:
            return None
        try:
            info = info_getter()
        except (OSError, AttributeError, NotImplementedError):  # pragma: no cover - diagnostic only
            return None
        return (info.srWindow.Left, info.srWindow.Top, info.dwSize.X, info.dwSize.Y)

    def measure(self, generation: int, reserved_rows: int) -> Geometry:
        """Take a fresh geometry snapshot.

        Sampling happens at every activation and reconfiguration. Geometry frozen at
        construction is wrong the moment the window is resized.

        :param generation: the generation number to stamp on the snapshot
        :param reserved_rows: rows to withhold at the bottom
        :return: the snapshot
        """
        size = self.physical_size()
        return Geometry(
            generation=generation,
            physical_rows=size.rows,
            columns=size.columns,
            reserved_rows=reserved_rows,
            buffer_id=self.buffer_id(),
        )

    def write_margin_change(self, sequence: str) -> None:
        """Emit a margin change without moving the cursor.

        DECSTBM homes the cursor on set *and* on reset, so an unwrapped margin change drops
        rendering at the top of the screen and overwrites what is already there.

        :param sequence: the margin sequence to emit
        """
        self._output.write_raw(f"{cursor_save_sequence()}{sequence}{cursor_restore_sequence()}")
        # write_raw only appends to the backend's own buffer; the terminal has to see this
        # now rather than whenever something else happens to flush.
        self._output.flush()

    def install_region(self, geometry: Geometry) -> None:
        """Install the scroll region described by ``geometry``.

        :param geometry: the snapshot to install margins for
        :raises ValueError: if the geometry is not eligible for a reservation
        """
        self.write_margin_change(scroll_region_sequence(geometry.physical_rows, geometry.reserved_rows))

    def release_region(self) -> None:
        """Restore full-screen scroll margins."""
        self.write_margin_change(reset_scroll_region_sequence())


class TerminalDisplay:
    """Owns the reservation for the lifetime of one command loop.

    Acquisition is re-entrant: nested leases share one reservation and only the outermost
    release tears it down. Release is idempotent, runs on the exception path, and always
    restores full-screen margins -- leaving them installed would make every later line of
    shell output scroll inside a region the shell knows nothing about.
    """

    def __init__(self, output: "Output", reserved_rows: int = 1) -> None:
        """Prepare a display over the given backend.

        :param output: the original, unwrapped output object
        :param reserved_rows: rows to withhold at the bottom of the screen
        :raises ValueError: if fewer than one row is reserved
        """
        if reserved_rows < 1:
            raise ValueError(f"reserved_rows must be at least 1, got {reserved_rows}")
        self._terminal = PhysicalTerminal(output)
        self._reserved_rows = reserved_rows
        self._generation = 0
        self._geometry: Geometry | None = None
        self._depth = 0
        self._adapter: Any = None
        self._handoff_geometry: Geometry | None = None

    @property
    def terminal(self) -> PhysicalTerminal:
        """The unwrapped physical terminal."""
        return self._terminal

    @property
    def geometry(self) -> Geometry | None:
        """The current geometry snapshot, or ``None`` while released."""
        return self._geometry

    @property
    def is_reserved(self) -> bool:
        """Whether a reservation is currently installed."""
        return self._geometry is not None

    @property
    def output(self) -> "Output":
        """The output callers should render through: the adapter while reserved, else the backend."""
        if self._adapter is not None and self._geometry is not None:
            return self._adapter  # type: ignore[no-any-return]
        return self._terminal.output

    @property
    def lease_depth(self) -> int:
        """How many nested leases are currently held."""
        return self._depth

    def _measure(self) -> Geometry:
        """Take the next geometry snapshot, advancing the generation.

        :return: the new snapshot
        """
        self._generation += 1
        return self._terminal.measure(self._generation, self._reserved_rows)

    def acquire(self) -> bool:
        """Install the reservation, or take a nested lease on one already installed.

        A terminal too short for the floor is not an error and not a degraded mode: the lease
        is granted, no region is installed, and callers see full geometry through the
        original backend until the terminal grows.

        :return: whether a reservation is installed after this call
        """
        self._depth += 1
        if self._depth > 1:
            return self.is_reserved
        if not self._terminal.supports_reservation:
            return False

        try:
            geometry = self._measure()
            if not geometry.is_eligible:
                return False
            self._terminal.install_region(geometry)
        except BaseException:
            # Give the lease back *first*. Cleanup can fail too -- a terminal that could not
            # be measured or written to may well refuse the reset as well -- and a lease
            # stranded by that failure makes every later acquire() a no-op at depth two,
            # which never retries the installation and never reports why.
            self._depth -= 1
            # Never leave margins half-installed; a failed acquisition falls back to ordinary
            # full-screen rendering rather than to an unknown terminal state. If even that
            # write fails there is nothing further to try, and the original error is the one
            # worth propagating.
            with suppress(Exception):
                self._terminal.release_region()
            raise

        self._geometry = geometry
        self._adapter = self._make_adapter()
        return True

    def _make_adapter(self) -> Any:
        """Build the virtual output for the active reservation.

        :return: the adapter to render through
        """
        from .reserved_output import ReservedOutput

        return ReservedOutput(self._terminal.output, self)

    def release(self) -> None:
        """Drop one lease, tearing the reservation down when the last one goes.

        Calling this while already released does nothing, so cleanup paths may call it freely.
        """
        if self._depth == 0:
            return
        self._depth -= 1
        if self._depth > 0:
            return
        self._teardown()

    def _teardown(self) -> None:
        """Restore full-screen margins and drop the adapter."""
        self._adapter = None
        self._handoff_geometry = None
        if self._geometry is None:
            return
        self._geometry = None
        self._terminal.release_region()

    def reconfigure(self) -> bool:
        """Resample the terminal and re-establish the reservation for the new geometry.

        Used after a resize. A terminal that has shrunk below the floor releases rather than
        narrowing, and one that has grown back above it reacquires.

        :return: whether a reservation is installed after this call
        """
        if self._depth == 0:
            return False
        if self._handoff_geometry is not None:
            # A handoff keeps the lease deliberately, so lease depth alone does not mean the
            # terminal is ours. Reinstalling margins here would restrict the screen of the
            # program currently owning it. The resize is not lost: the return path measures
            # afresh rather than restoring the snapshot taken before the handoff.
            return False
        geometry = self._measure()
        if not geometry.is_eligible or not self._terminal.supports_reservation:
            if self._geometry is not None:
                self._geometry = None
                self._adapter = None
                self._terminal.release_region()
            return False
        self._terminal.install_region(geometry)
        self._geometry = geometry
        if self._adapter is None:
            self._adapter = self._make_adapter()
        return True

    def release_region_for_handoff(self) -> None:
        """Restore full-screen margins for a program taking the terminal over.

        The reservation is remembered rather than dropped: the lease is still held, and
        :meth:`reacquire_region_after_handoff` puts the region back afterwards. The two screen
        buffers keep separate margin state and the program taking over knows nothing about a
        reservation, so the main buffer is left as the shell expects it.
        """
        if self._geometry is None:
            return
        self._handoff_geometry = self._geometry
        self._geometry = None
        self._terminal.release_region()

    def reacquire_region_after_handoff(self) -> None:
        """Re-establish the reservation after a program hands the terminal back.

        Geometry is measured afresh rather than restored from the snapshot taken before the
        handoff: the program in between may have resized the window, and a region installed
        from a stale height puts the toolbar somewhere other than the bottom row.
        """
        if self._handoff_geometry is None or self._depth == 0:
            return
        self._handoff_geometry = None
        geometry = self._measure()
        if not geometry.is_eligible:
            # The terminal shrank while the guest had it. Nothing is installed, so callers
            # go back to the plain backend -- which they do by way of the geometry check in
            # `output`, rather than by unbinding the adapter here, so that a terminal which
            # grows again reuses the same object.
            return
        self._terminal.install_region(geometry)
        self._geometry = geometry

    def revalidate_viewport(self) -> bool:
        """Re-check the viewport origin and rebuild the region if it moved.

        A moved viewport makes absolute row numbers address different cells even when width
        and height have not changed, so it invalidates the generation on its own.

        :return: whether a reservation is installed after this call
        """
        if self._geometry is None:
            return False
        if self._terminal.buffer_id() == self._geometry.buffer_id:
            return True
        return self.reconfigure()

    def __enter__(self) -> Self:
        """Acquire a lease."""
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the lease, including when the body raised."""
        self.release()
