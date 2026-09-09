"""Record a renderer's output operations instead of performing them.

prompt-toolkit's ``Renderer.render()`` evaluates the application's layout, filters and styles
*while* it emits. Holding the terminal lock around that whole call would run application
callbacks inside the transaction, which the wait contract forbids and which is how a toolbar
callback ends up deadlocking against the thread that is painting it.

The way out is to separate preparation from emission. The renderer runs against a
:class:`RecordingOutput`, which answers its questions from facts captured beforehand and
writes its operations to a list. The resulting :class:`OperationBatch` is replayed onto the
real backend later, inside one terminal transaction, once the bridge has revalidated that the
frame is still current.

Two properties make the recording safe to build off-lock:

**It never touches a backend.** The recorder holds no output object at all -- only an
immutable :class:`PreflightFacts`. Using the real backend as a recording sink would advance
its buffered text, attribute and cursor caches and console modes, so a discarded frame would
leave the backend believing things about the terminal that were never emitted.

**Reads are answered, not deferred.** The renderer asks for the size and for the rows below
the cursor mid-render and branches on the answers. Those come from the preflight snapshot, so
every operation in a batch was decided against one consistent view of the terminal -- the same
view the bridge revalidates before replaying it.

A batch is a delay, not a translation: replaying it produces exactly the bytes the backend
would have produced had the renderer written to it directly.
"""

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import ColorDepth, Output

if TYPE_CHECKING:  # pragma: no cover
    from prompt_toolkit.cursor_shapes import CursorShape
    from prompt_toolkit.styles import Attrs


class UnrecordableOperationError(RuntimeError):
    """Raised for an operation that cannot be deferred to commit time.

    Screen-buffer transitions and viewport moves change what every later coordinate means.
    They are ownership boundaries, taken explicitly before a frame is prepared for the new
    screen, so meeting one during preparation means a frame is being prepared against a
    terminal that is no longer the one it was measured on.
    """


@dataclass(frozen=True)
class PreflightFacts:
    """The terminal as one preparation saw it, captured before recording begins.

    Everything the renderer can *ask* is here, so recording needs no backend. Capturing these
    is a short serialized read with no application callbacks in it.
    """

    #: The size the application is rendering against, already reservation-adjusted.
    size: Size

    #: Native rows below the cursor, or ``None`` where the backend has no such notion and the
    #: renderer must fall back to a cursor-position report.
    rows_below_cursor: int | None

    #: The backend's encoding.
    encoding: str

    #: The backend's default color depth.
    default_color_depth: ColorDepth

    #: Whether the backend answers cursor-position reports.
    responds_to_cpr: bool

    #: The backend's file descriptor, or ``None`` where it has none.
    fileno: int | None

    @classmethod
    def capture(cls, output: Output) -> "PreflightFacts":
        """Read every fact a recorded render may need, without writing anything.

        :param output: the backend to read from
        :return: the captured facts
        """
        try:
            rows_below: int | None = output.get_rows_below_cursor_position()
        except NotImplementedError:
            rows_below = None
        try:
            descriptor: int | None = output.fileno()
        except (io.UnsupportedOperation, AttributeError, OSError):
            descriptor = None
        return cls(
            size=output.get_size(),
            rows_below_cursor=rows_below,
            encoding=output.encoding(),
            default_color_depth=output.get_default_color_depth(),
            responds_to_cpr=output.responds_to_cpr,
            fileno=descriptor,
        )


@dataclass(frozen=True)
class Operation:
    """One recorded output call, ready to be replayed by name onto a real backend."""

    #: The :class:`~prompt_toolkit.output.Output` method that was called.
    name: str

    #: Its positional arguments. Output's interface takes no keyword-only arguments.
    args: tuple[Any, ...] = ()

    def replay(self, output: Output) -> None:
        """Perform this operation on a real backend.

        :param output: the backend to emit through
        """
        getattr(output, self.name)(*self.args)


@dataclass(frozen=True)
class OperationBatch:
    """An immutable, ordered recording of one prepared frame.

    Immutability is what makes commit-time validation meaningful: a batch that could still
    grow after it was validated would be replayed as something other than what was checked.
    """

    #: The operations to replay, in the order the renderer made them.
    operations: tuple[Operation, ...]

    #: The terminal facts the operations were decided against.
    facts: PreflightFacts

    def replay(self, output: Output) -> None:
        """Replay every operation onto a real backend, in order.

        Replay deliberately does not catch anything. A failure part-way through means some
        bytes have already reached the terminal and others have not, which is a physical state
        the caller has to recover from -- swallowing the exception here would hide exactly the
        case that needs handling.

        :param output: the backend to emit through
        :raises Exception: whatever the backend raises, after the earlier operations have run
        """
        for operation in self.operations:
            operation.replay(output)


class RecordingOutput(Output):
    """An :class:`~prompt_toolkit.output.Output` that records rather than emits.

    Every abstract method is written out. Answering by ``__getattr__`` would leave the class
    abstract, and would silently record whatever prompt-toolkit adds next without anyone
    deciding whether it is safe to defer.
    """

    #: Marks this as a recorder so the physical layer refuses to wrap it.
    is_reserved_adapter = True

    def __init__(self, facts: PreflightFacts) -> None:
        """Record a frame against a fixed view of the terminal.

        :param facts: the preflight snapshot to answer reads from
        """
        self._facts = facts
        self._operations: list[Operation] = []
        # Output declares stdout as writable. There is no stream to offer here, and offering
        # the real one would invite a caller to write around the recording.
        self.stdout = None

    @property
    def facts(self) -> PreflightFacts:
        """The preflight snapshot this frame was recorded against."""
        return self._facts

    @property
    def operations(self) -> tuple[Operation, ...]:
        """The operations recorded so far, in order."""
        return tuple(self._operations)

    def batch(self) -> OperationBatch:
        """Freeze what has been recorded so far into a replayable batch.

        :return: the immutable batch
        """
        return OperationBatch(operations=self.operations, facts=self._facts)

    def _record(self, name: str, *args: Any) -> None:
        """Append one operation to the recording.

        :param name: the output method that was called
        :param args: its positional arguments
        """
        self._operations.append(Operation(name, args))

    # -- reads, answered from the preflight snapshot ---------------------------------------

    def get_size(self) -> Size:
        """Report the size this frame is being prepared against."""
        return self._facts.size

    def get_rows_below_cursor_position(self) -> int:
        """Report the native row count, or raise as a backend without one would.

        :return: rows below the cursor within the usable region
        :raises NotImplementedError: if the backend has no native answer
        """
        if self._facts.rows_below_cursor is None:
            raise NotImplementedError
        return self._facts.rows_below_cursor

    def encoding(self) -> str:
        """Report the backend's encoding."""
        return self._facts.encoding

    def get_default_color_depth(self) -> ColorDepth:
        """Report the backend's default color depth."""
        return self._facts.default_color_depth

    @property
    def responds_to_cpr(self) -> bool:
        """Whether the backend answers cursor-position reports."""
        return self._facts.responds_to_cpr

    def fileno(self) -> int:
        """Report the backend's file descriptor.

        :return: the descriptor
        :raises io.UnsupportedOperation: if the backend has none
        """
        if self._facts.fileno is None:
            raise io.UnsupportedOperation("the recorded backend has no file descriptor")
        return self._facts.fileno

    # -- ownership boundaries, which cannot be deferred ------------------------------------

    def enter_alternate_screen(self) -> None:
        """Refuse to record a switch to the alternate screen.

        :raises UnrecordableOperationError: always
        """
        raise UnrecordableOperationError(
            "entering the alternate screen is an ownership transition and cannot be recorded in a frame"
        )

    def quit_alternate_screen(self) -> None:
        """Refuse to record a return to the main screen.

        :raises UnrecordableOperationError: always
        """
        raise UnrecordableOperationError(
            "leaving the alternate screen is an ownership transition and cannot be recorded in a frame"
        )

    def scroll_buffer_to_prompt(self) -> None:
        """Refuse to record a viewport move.

        :raises UnrecordableOperationError: always
        """
        raise UnrecordableOperationError("moving the viewport invalidates the geometry this frame was prepared against")

    # -- recorded operations ---------------------------------------------------------------

    def write(self, data: str) -> None:
        """Record a text write.

        :param data: the text
        """
        self._record("write", data)

    def write_raw(self, data: str) -> None:
        """Record a raw write.

        :param data: the raw data
        """
        self._record("write_raw", data)

    def flush(self) -> None:
        """Record a flush boundary."""
        self._record("flush")

    def set_title(self, title: str) -> None:
        """Record a title change.

        :param title: the title
        """
        self._record("set_title", title)

    def clear_title(self) -> None:
        """Record clearing the title."""
        self._record("clear_title")

    def erase_screen(self) -> None:
        """Record a screen erase."""
        self._record("erase_screen")

    def erase_down(self) -> None:
        """Record an erase from the cursor to the bottom."""
        self._record("erase_down")

    def erase_end_of_line(self) -> None:
        """Record an erase to the end of the line."""
        self._record("erase_end_of_line")

    def set_attributes(self, attrs: "Attrs", color_depth: ColorDepth) -> None:
        """Record an attribute change.

        :param attrs: the attributes
        :param color_depth: the color depth to render them at
        """
        self._record("set_attributes", attrs, color_depth)

    def reset_attributes(self) -> None:
        """Record an attribute reset."""
        self._record("reset_attributes")

    def disable_autowrap(self) -> None:
        """Record turning automatic wrapping off."""
        self._record("disable_autowrap")

    def enable_autowrap(self) -> None:
        """Record turning automatic wrapping on."""
        self._record("enable_autowrap")

    def cursor_goto(self, row: int = 0, column: int = 0) -> None:
        """Record a cursor move.

        :param row: zero-based row
        :param column: zero-based column
        """
        self._record("cursor_goto", row, column)

    def cursor_up(self, amount: int) -> None:
        """Record moving the cursor up.

        :param amount: rows to move
        """
        self._record("cursor_up", amount)

    def cursor_down(self, amount: int) -> None:
        """Record moving the cursor down.

        :param amount: rows to move
        """
        self._record("cursor_down", amount)

    def cursor_forward(self, amount: int) -> None:
        """Record moving the cursor right.

        :param amount: columns to move
        """
        self._record("cursor_forward", amount)

    def cursor_backward(self, amount: int) -> None:
        """Record moving the cursor left.

        :param amount: columns to move
        """
        self._record("cursor_backward", amount)

    def hide_cursor(self) -> None:
        """Record hiding the cursor."""
        self._record("hide_cursor")

    def show_cursor(self) -> None:
        """Record showing the cursor."""
        self._record("show_cursor")

    def set_cursor_shape(self, cursor_shape: "CursorShape") -> None:
        """Record a cursor-shape change.

        :param cursor_shape: the shape
        """
        self._record("set_cursor_shape", cursor_shape)

    def reset_cursor_shape(self) -> None:
        """Record restoring the default cursor shape."""
        self._record("reset_cursor_shape")

    def enable_mouse_support(self) -> None:
        """Record turning mouse reporting on."""
        self._record("enable_mouse_support")

    def disable_mouse_support(self) -> None:
        """Record turning mouse reporting off."""
        self._record("disable_mouse_support")

    def enable_bracketed_paste(self) -> None:
        """Record turning bracketed paste on."""
        self._record("enable_bracketed_paste")

    def disable_bracketed_paste(self) -> None:
        """Record turning bracketed paste off."""
        self._record("disable_bracketed_paste")

    def reset_cursor_key_mode(self) -> None:
        """Record restoring the default cursor-key mode."""
        self._record("reset_cursor_key_mode")

    def ask_for_cpr(self) -> None:
        """Record a cursor-position request.

        The request is emitted when the batch is replayed, in its recorded position, so the
        bridge that owns pending-request correlation registers it at commit time rather than
        while a frame is still provisional.
        """
        self._record("ask_for_cpr")

    def bell(self) -> None:
        """Record ringing the bell."""
        self._record("bell")
