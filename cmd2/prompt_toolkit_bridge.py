"""Prepare, commit and recover prompt-toolkit renderer frames.

Upstream's renderer emits while it thinks. It evaluates the layout, resolves styles, decides a
height, writes the difference against its own last screen, and updates a dozen fields as it
goes -- all inside one call. Two consequences shape this module.

**Emission has to be separated from preparation.** The render runs against a recorder, off the
terminal lock, and produces an ordered batch. The bridge revalidates that batch against the
current geometry, output, owner and terminal generations and only then replays it, inside one
transaction. A command write, a resize, a handoff or an owner change between those two moments
retires the batch without emitting a byte of it.

**Discarding the output is only half of discarding the frame.** The renderer advanced its own
state while preparing: ``_last_screen`` became a baseline for a frame the terminal never
received, and the mode flags -- bracketed paste, mouse, cursor-key mode, cursor shape -- latch
next to their emission. A latched flag never re-emits its sequence, so a full repaint does not
repair it. Recovery therefore does two things: it drops the diff baseline, and it re-establishes
a small, explicitly enumerated terminal-state contract, physically, and then tells the renderer
what is now true.

This is deliberately not a snapshot-and-restore of upstream's fields, and deliberately not a
call to upstream's ``reset()``: that emits operations of its own and rewrites available-height
bookkeeping. It is a narrow initialization contract tied to a qualified prompt-toolkit version,
and :mod:`tests.test_prompt_toolkit_bridge` holds it to that version by name.
"""

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.mouse_handlers import MouseHandlers

from .output_recorder import OperationBatch, PreflightFacts, RecordingOutput
from .terminal_transaction import TerminalLock, assert_no_terminal_transaction

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from prompt_toolkit.application import Application
    from prompt_toolkit.renderer import Renderer

    from .terminal_display import TerminalDisplay


class ReservedModeFailureError(RuntimeError):
    """Raised when reserved rendering cannot continue safely.

    The caller's answer to this is to release the reservation and fall back to compatibility
    rendering -- after the release, never before it. Continuing to emit into a terminal whose
    state cannot be established is how a prompt ends up drawn over committed output.
    """


@dataclass(frozen=True)
class Generations:
    """What a prepared frame was prepared against.

    Every field is something that changes where or how the frame's operations would land.
    Content is *not* here: a toolbar content change must never authorize an otherwise stale
    batch, so it is tracked separately.
    """

    #: The geometry snapshot's generation.
    geometry: int

    #: Identity of the output object the frame was recorded against.
    output: int

    #: Which UI owner prepared it.
    owner: int

    #: Bumped by every managed write, clear or handoff that reaches the terminal.
    terminal: int


@dataclass(frozen=True)
class PreparedRender:
    """One recorded frame and the generations it must still match to be emitted."""

    #: The operations to replay.
    batch: OperationBatch

    #: What the frame was prepared against.
    generations: Generations


@dataclass(frozen=True)
class TerminalModePolicy:
    """The modes the current owner wants established, evaluated on the UI thread.

    Resolving these runs application filters, so it happens before the transaction rather than
    between two writes to the terminal.
    """

    #: Whether mouse reporting should be on, per the renderer's filter.
    mouse_support: bool


class PromptToolkitBridge:
    """Binds one renderer to the reserved terminal, and owns what is known about it."""

    def __init__(self, renderer: "Renderer", display: "TerminalDisplay", lock: TerminalLock) -> None:
        """Bind to a renderer and the display that owns the reservation.

        :param renderer: the application's renderer
        :param display: the owner of the reservation and its geometry
        :param lock: the terminal transaction lock shared by all cmd2-controlled output
        """
        self._renderer = renderer
        self._display = display
        self._lock = lock
        self._owner_generation = 0
        self._terminal_generation = 0
        self._content_generation = 0
        self._in_flight: PreparedRender | None = None
        self._committed: Generations | None = None
        self._needs_resynchronization = False
        self._reserved_emission_stopped = False
        self._redraw_pending = False
        self._redraw_scheduler: Callable[[], None] | None = None
        self._pending_error: BaseException | None = None
        self._prompt_anchor: int | None = None
        self._resynchronization_reason: str | None = None
        self._pending_cpr: deque[int] = deque()

    # -- what is known ---------------------------------------------------------------------

    @property
    def needs_resynchronization(self) -> bool:
        """Whether recovery is owed before another frame may be prepared."""
        return self._needs_resynchronization

    @property
    def reserved_emission_stopped(self) -> bool:
        """Whether reserved rendering has been abandoned after unrecoverable failure."""
        return self._reserved_emission_stopped

    @property
    def can_dispatch_input(self) -> bool:
        """Whether input and after-render notifications may consume the renderer's state.

        False while a frame is in flight: its mouse handlers, visible windows and cursor
        position describe a screen the terminal has not been shown.
        """
        return not (self._needs_resynchronization or self._reserved_emission_stopped or self._in_flight is not None)

    @property
    def resynchronization_reason(self) -> str | None:
        """Why recovery is owed, for diagnostics, or ``None`` when none is."""
        return self._resynchronization_reason

    @property
    def redraw_pending(self) -> bool:
        """Whether a redraw has been requested and not yet served."""
        return self._redraw_pending

    @property
    def content_generation(self) -> int:
        """How many times the toolbar's content has been invalidated."""
        return self._content_generation

    @property
    def prompt_anchor(self) -> int | None:
        """The physical row the prompt is known to start on, or ``None``."""
        return self._prompt_anchor

    def generations(self) -> Generations:
        """Snapshot what a frame prepared now would have to match at commit.

        :return: the current generations
        """
        geometry = self._display.geometry
        return Generations(
            geometry=geometry.generation if geometry is not None else 0,
            output=id(self._display.output),
            owner=self._owner_generation,
            terminal=self._terminal_generation,
        )

    def take_pending_error(self) -> BaseException | None:
        """Take the failure waiting to be reported, if there is one.

        :return: the error to report once, or ``None``
        """
        error, self._pending_error = self._pending_error, None
        return error

    # -- invalidation ----------------------------------------------------------------------

    def set_redraw_scheduler(self, scheduler: "Callable[[], None]") -> None:
        """Install the callback that asks the UI owner for another frame.

        :param scheduler: called once per coalesced redraw request
        """
        self._redraw_scheduler = scheduler

    def note_managed_write(self) -> None:
        """Record that managed output reached the terminal."""
        self._terminal_generation += 1
        self._request_redraw()

    def note_owner_change(self) -> None:
        """Record that a different UI owner now holds the terminal."""
        self._owner_generation += 1
        self._request_redraw()

    def note_geometry_change(self) -> None:
        """Record that the terminal's geometry changed under us."""
        self.require_resynchronization("the geometry changed")
        self._request_redraw()

    def note_content_change(self) -> None:
        """Record that the toolbar's content changed.

        This deliberately does not touch the generations a renderer batch is validated
        against: a content change is not a reason to emit a frame prepared against a terminal
        that has since moved on.
        """
        self._content_generation += 1

    def require_resynchronization(self, reason: str) -> None:
        """Mark that recovery is owed before anything else may be rendered.

        :param reason: why, for diagnostics
        """
        self._needs_resynchronization = True
        self._resynchronization_reason = reason
        self._retire()

    def stop_reserved_emission(self, error: BaseException) -> None:
        """Abandon reserved rendering after a failure that could not be cleaned up.

        :param error: what went wrong, to be reported once
        """
        self._reserved_emission_stopped = True
        self._pending_error = error
        self._retire()

    def set_prompt_anchor(self, physical_row: int) -> None:
        """Record the physical row the prompt starts on.

        :param physical_row: the one-based row
        """
        self._prompt_anchor = physical_row

    def forget_prompt_anchor(self) -> None:
        """Record that the prompt's origin is no longer known."""
        self._prompt_anchor = None

    def _request_redraw(self) -> None:
        """Ask the owner for another frame, coalescing repeated requests into one."""
        if self._redraw_pending:
            return
        self._redraw_pending = True
        if self._redraw_scheduler is not None:
            self._redraw_scheduler()

    def _retire(self) -> None:
        """Drop the in-flight frame and the baseline it would have become."""
        self._in_flight = None
        self._renderer._last_screen = None

    # -- prepare and commit ----------------------------------------------------------------

    def prepare(self, app: "Application[Any]") -> PreparedRender | None:
        """Record a full renderer frame without emitting anything.

        :param app: the application to render
        :return: the prepared frame, or ``None`` if one cannot be prepared right now
        """
        assert_no_terminal_transaction("preparing a renderer frame")
        if self._reserved_emission_stopped or self._needs_resynchronization or self._in_flight is not None:
            return None

        with self._lock.transaction("preflight"):
            facts = PreflightFacts.capture(self._display.output)
        generations = self.generations()

        recorder = RecordingOutput(facts)
        original = self._renderer.output
        self._renderer.output = recorder
        try:
            self._renderer.render(app, app.layout)
        except Exception as error:  # noqa: BLE001 - a layout callback must not end a command
            self._pending_error = error
            self.require_resynchronization("preparing the frame raised")
            return None
        finally:
            self._renderer.output = original

        prepared = PreparedRender(batch=recorder.batch(), generations=generations)
        self._in_flight = prepared
        return prepared

    def commit(self, prepared: PreparedRender) -> bool:
        """Revalidate a prepared frame and, if it is still current, emit it.

        :param prepared: the frame to commit
        :return: whether the frame was emitted in full
        """
        assert_no_terminal_transaction("committing a prepared frame")
        if prepared is not self._in_flight:
            # Already retired, or from a previous attempt. Replaying it would emit a frame
            # nothing has validated, and possibly emit it twice.
            return False

        with self._lock.transaction("commit", generation=prepared.generations.geometry):
            if self.generations() != prepared.generations:
                self.require_resynchronization("the terminal changed between preparing and committing")
                return False
            try:
                prepared.batch.replay(self._display.output)
                self._display.output.flush()
            except Exception as error:  # noqa: BLE001 - the terminal's state is now unknown
                # Some of the batch reached the terminal and some did not, and nothing here
                # knows where the boundary was. The frame is never replayed: a retry would
                # duplicate whatever already landed.
                self._pending_error = error
                self.require_resynchronization("a frame was only partly emitted")
                self._attempt_cleanup()
                return False

        self._in_flight = None
        self._committed = prepared.generations
        self._redraw_pending = False
        return True

    def _attempt_cleanup(self) -> bool:
        """Bring the terminal back to a known state after a partial commit.

        :return: whether a known state was re-established
        """
        try:
            output = self._display.output
            output.reset_attributes()
            output.enable_autowrap()
            output.flush()
            self._display.reconfigure()
        except Exception as error:  # noqa: BLE001 - cleanup failing is itself the answer
            self._reserved_emission_stopped = True
            self._pending_error = error
            return False
        return True

    # -- recovery --------------------------------------------------------------------------

    def resynchronize(self) -> None:
        """Re-establish a known terminal state and a known prompt origin.

        Call this on the UI owner's thread: the mode policy is resolved from application
        filters, which need the application's context and must not run under the lock.

        :raises ReservedModeFailureError: if reserved rendering has stopped, or no prompt
            origin can be established at all
        """
        assert_no_terminal_transaction("resynchronizing the terminal")
        if self._reserved_emission_stopped:
            raise ReservedModeFailureError("reserved emission has stopped; release before rendering again")

        policy = self._desired_policy()
        origin = self._prompt_anchor
        if origin is None:
            if not self._display.output.responds_to_cpr:
                raise ReservedModeFailureError("the prompt's origin is unknown and the terminal does not report its cursor")
            # The reply establishes the origin. Recovery stays owed until it arrives; guessing
            # would repaint the prompt over committed output.
            self.request_cursor_position()
            return

        with self._lock.transaction("resynchronize"):
            output = self._display.output
            output.write_raw(f"\x1b[{origin};1H")
            # Upstream enables bracketed paste on every render and latches a flag beside the
            # emission, so the policy here is not conditional: it is on, and the flag is made
            # to agree with an enable that actually reached the terminal.
            output.enable_bracketed_paste()
            if policy.mouse_support:
                output.enable_mouse_support()
            else:
                output.disable_mouse_support()
            output.reset_cursor_key_mode()
            output.reset_attributes()
            output.enable_autowrap()
            output.reset_cursor_shape()
            output.show_cursor()
            output.flush()
            self._initialize_renderer(policy)

        self._needs_resynchronization = False
        self._resynchronization_reason = None
        self._in_flight = None

    def _desired_policy(self) -> TerminalModePolicy:
        """Evaluate the current owner's mode policy, off the terminal lock.

        :return: the policy to establish
        """
        return TerminalModePolicy(mouse_support=bool(self._renderer.mouse_support()))

    def _initialize_renderer(self, policy: TerminalModePolicy) -> None:
        """Tell the renderer what the terminal now is.

        This is the version-specific half of recovery. Each assignment answers a field that
        upstream advances during rendering and never re-checks: the diff baseline and its size
        and style, the latched mode flags, the believed cursor position that a full repaint
        moves *from*, the mouse handlers a discarded frame published, and the available-height
        bookkeeping that a visible toolbar says nothing about.

        :param policy: the policy just established physically
        """
        renderer = self._renderer
        renderer._bracketed_paste_enabled = True
        renderer._mouse_support_enabled = policy.mouse_support
        renderer._cursor_key_mode_reset = True
        # Cleared rather than set: the shape was reset physically, and clearing the cache is
        # what makes the next frame establish the application's own shape again.
        renderer._last_cursor_shape = None
        renderer._cursor_pos = Point(x=0, y=0)
        renderer._last_screen = None
        renderer._last_size = None
        renderer._last_style = None
        renderer.mouse_handlers = MouseHandlers()
        renderer._min_available_height = 0

    # -- cursor position reports -----------------------------------------------------------

    def request_cursor_position(self) -> bool:
        """Ask the terminal where the cursor is, in its own transaction.

        The request is never emitted inside another transaction. A paint temporarily occupies
        the band and restores the cursor afterwards; a request made in the middle of one would
        be answered with the painter's cursor, not the prompt's.

        :return: whether a request was emitted
        """
        assert_no_terminal_transaction("requesting a cursor position report")
        output = self._display.output
        if not output.responds_to_cpr:
            return False
        generation = self.generations().geometry
        with self._lock.transaction("cursor position request", generation=generation):
            output.ask_for_cpr()
            output.flush()
        self._pending_cpr.append(generation)
        return True

    def report_cursor_row(self, row: int) -> bool:
        """Take a cursor-position reply, in physical coordinates.

        Replies carry no generation on the wire, so they are correlated by order against the
        requests this bridge made. A reply from before a geometry change describes a screen
        that no longer exists and must not satisfy the request made after it.

        A row inside the reserved band is the failure named in the design: upstream would
        compute ``U - r + 1``, which is zero at the first reserved row and negative below it,
        and would leave the prompt's height silently invalid rather than raising.

        :param row: the one-based physical row the terminal reported
        :return: whether the reply was accepted and used
        """
        if not self._pending_cpr:
            # Nothing outstanding: a late reply from a stream that was already drained. It
            # must not be allowed to answer a request that was never made.
            self._settle_renderer_cpr()
            return False
        generation = self._pending_cpr.popleft()
        if generation != self.generations().geometry:
            self._settle_renderer_cpr()
            return False

        geometry = self._display.geometry
        usable = geometry.usable_rows if geometry is not None else self._display.output.get_size().rows
        if not 1 <= row <= usable:
            self._settle_renderer_cpr()
            self.require_resynchronization(f"cursor position report row {row} is inside the reserved band")
            return False

        self._prompt_anchor = row
        self._renderer.report_absolute_cursor_row(row)
        return True

    def _settle_renderer_cpr(self) -> None:
        """Resolve one of the renderer's own pending reports, if it has any.

        A rejected reply still has to settle the bookkeeping it would have settled. Left
        pending, the renderer waits for a report that is never coming.
        """
        futures = self._renderer._waiting_for_cpr_futures
        if futures:
            futures.popleft().set_result(None)
