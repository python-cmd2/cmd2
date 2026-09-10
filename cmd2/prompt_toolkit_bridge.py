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
        self._preparing = False
        self._committed: Generations | None = None
        self._needs_resynchronization = False
        self._reserved_emission_stopped = False
        self._redraw_pending = False
        self._redraw_scheduler: Callable[[], None] | None = None
        self._pending_error: BaseException | None = None
        self._prompt_anchor: int | None = None
        self._resynchronization_reason: str | None = None
        # One entry per outstanding request, in the order they went out. An entry is ``None``
        # once the screen it asked about is gone: the reply is still coming, so the place has
        # to be kept, but nothing it says can be believed.
        self._pending_cpr: deque[Generations | None] = deque()
        # The renderer methods this bridge replaced, by name, empty while unbound. Kept so
        # preparation can call the real render: calling the attribute would re-enter the
        # wrapper and never terminate.
        self._originals: dict[str, Any] = {}
        # What this bridge put in their place, so teardown can tell its own replacements from
        # something another caller installed afterwards.
        self._installed: dict[str, Any] = {}
        self._bound_app: Application[Any] | None = None
        self._emission_stopped_handler: Callable[[], None] | None = None
        self._frame_committed_handler: Callable[[], object] | None = None
        self._render_attempted_handler: Callable[[], object] | None = None
        # Whether the last thing this bridge tried to emit actually reached the terminal.
        self._last_emission_committed = False
        self._after_render_event: Any = None
        self._after_render_original: Any = None
        self._after_render_installed: Any = None

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

        False from the moment a preparation starts: the renderer's mouse handlers, visible
        windows and cursor position describe a screen the terminal has not been shown, and
        they are provisional from the first layout callback -- not merely once the render
        call returns.
        """
        return not (
            self._needs_resynchronization or self._reserved_emission_stopped or self._preparing or self._in_flight is not None
        )

    @property
    def resynchronization_reason(self) -> str | None:
        """Why recovery is owed, for diagnostics, or ``None`` when none is."""
        return self._resynchronization_reason

    @property
    def in_flight(self) -> PreparedRender | None:
        """The frame prepared but not yet committed, if there is one."""
        return self._in_flight

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

    def note_managed_write(self, prompt_anchor: int | None = None) -> None:
        """Record that managed output reached the terminal.

        This invalidates the committed baseline rather than only bumping a generation.
        Generation comparison catches a write that lands *during* a preparation, but a write
        between two frames leaves the renderer believing its last screen is still displayed
        and its cursor still where that screen ended -- and the output just emitted moved the
        cursor, and may have scrolled everything above it. The next frame would be diffed
        against a screen the terminal no longer shows, from an origin it no longer has.

        :param prompt_anchor: the physical row the prompt now starts on, where the layer that
            emitted the output knows it. Passing nothing *forgets* the origin rather than
            keeping the old one: the write moved the cursor and may have scrolled the screen,
            so the remembered row is exactly what is no longer true, and recovery asks the
            terminal instead.
        """
        self._terminal_generation += 1
        self._prompt_anchor = prompt_anchor
        self.require_resynchronization("managed output reached the terminal")
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

    def set_frame_committed_handler(self, handler: "Callable[[], object]") -> None:
        """Install what to call after a frame has actually reached the terminal.

        Runs off the lock and only for a committed frame. Upstream's own after-render event
        fires during preparation, when the frame exists only as a recording, so it cannot
        answer "has the user seen this".

        :param handler: called after each committed frame; its return value is ignored
        """
        self._frame_committed_handler = handler

    def set_render_attempted_handler(self, handler: "Callable[[], object] | None") -> None:
        """Install what to call after each render attempt, whatever came of it.

        Distinct from the committed-frame handler on purpose. "A frame reached the terminal"
        and "the renderer has been through a frame" are different facts, and something waiting
        for the display to start needs the second: a frame skipped while recovery is owed
        still means the application is running and rendering.

        :param handler: called after every render attempt, or ``None`` to remove it
        """
        self._render_attempted_handler = handler

    def set_emission_stopped_handler(self, handler: "Callable[[], None]") -> None:
        """Install what to call when reserved rendering has to be abandoned.

        The owner of the reservation is what runs here: rendering cannot resume until the rows
        have been given back and this bridge unbound, and only the owner can do either.

        :param handler: called once, when emission is abandoned
        """
        self._emission_stopped_handler = handler

    def stop_reserved_emission(self, error: BaseException) -> None:
        """Abandon reserved rendering after a failure that could not be cleaned up.

        :param error: what went wrong, to be reported once
        """
        if self._reserved_emission_stopped:
            return
        self._reserved_emission_stopped = True
        self._pending_error = error
        self._retire()
        if self._emission_stopped_handler is not None:
            self._emission_stopped_handler()

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

    # -- binding ---------------------------------------------------------------------------

    def bind(self, app: "Application[Any]") -> None:
        """Route the application's own renders through this bridge.

        prompt-toolkit renders from its event loop whenever it decides to, so intercepting is
        the only way those frames come under the transaction. The interception is installed on
        the renderer *instance* and removed again on the way out -- patching the class would
        change every renderer in the process, including ones cmd2 does not own.

        :param app: the application whose renders are being intercepted
        """
        if self._originals:
            return
        renderer = self._renderer
        replacements = {
            "render": self._render_through_bridge,
            "erase": self._erase_through_bridge,
            "clear": self._clear_through_bridge,
            # Upstream both asks for cursor reports and receives them: its own key binding
            # calls report_absolute_cursor_row when the reply arrives. Unrecorded, a request
            # would have its reply arrive uncorrelated and be discarded, leaving the prompt's
            # height unknown; unvalidated, a reply from inside the reserved band would set a
            # height of zero or less and never say so.
            "request_absolute_cursor_position": self._request_cursor_position_through_bridge,
            "report_absolute_cursor_row": self._report_cursor_row_through_bridge,
        }
        self._originals = {name: getattr(renderer, name) for name in replacements}
        self._installed = dict(replacements)
        self._bound_app = app
        # Upstream fires this after ``render()`` returns, whatever the wrapper decided to do,
        # so a frame the bridge skipped would still tell everything waiting on a rendered
        # frame that one had happened -- including the command display's readiness signal.
        self._after_render_event = app.after_render
        self._after_render_original = app.after_render.fire
        self._after_render_installed = self._fire_after_render_through_bridge
        # By name, as with the renderer's methods: this replacement belongs to this event
        # object, not to the class every application's events are built from.
        setattr(app.after_render, "fire", self._after_render_installed)  # noqa: B010
        for name, replacement in replacements.items():
            # Set by name so the replacement lands on this instance. Assigning the class
            # attribute would change every renderer in the process, including ones cmd2 does
            # not own.
            setattr(renderer, name, replacement)
        if self._redraw_scheduler is None:
            self._redraw_scheduler = app.invalidate

    def unbind(self) -> None:
        """Give the renderer its own methods back.

        Safe to call when nothing was bound: teardown reaches this from more than one place.
        """
        event, self._after_render_event = self._after_render_event, None
        if event is not None and getattr(event, "fire", None) == self._after_render_installed:
            setattr(event, "fire", self._after_render_original)  # noqa: B010
        self._after_render_original = None
        self._after_render_installed = None

        originals, self._originals = self._originals, {}
        installed, self._installed = self._installed, {}
        for name, original in originals.items():
            # Restored only where this bridge's replacement is still in place. Another caller
            # may have wrapped the renderer since -- for tracing, for a test -- and putting
            # the original back over theirs would silently undo it.
            if getattr(self._renderer, name, None) == installed.get(name):
                setattr(self._renderer, name, original)
        self._bound_app = None

    def _render_through_bridge(self, app: "Application[Any]", layout: Any, is_done: bool = False) -> None:
        """Prepare and commit one frame, telling anything waiting that an attempt was made.

        :param app: the application being rendered
        :param layout: the layout to render; upstream passes ``app.layout``
        :param is_done: whether this is the final frame of a prompt
        """
        try:
            self._render_frame(app, layout, is_done)
        finally:
            if self._render_attempted_handler is not None:
                self._render_attempted_handler()

    def _render_frame(self, app: "Application[Any]", layout: Any, is_done: bool = False) -> None:
        """Prepare and commit one frame in place of upstream's direct render.

        Runs on the UI thread, which is where recovery's callbacks belong too, so an owed
        recovery is done here rather than deferred: a frame prepared before the terminal has
        been resynchronized would be diffed against a screen nobody has seen.

        :param app: the application being rendered
        :param layout: the layout to render; upstream passes ``app.layout``
        :param is_done: whether this is the final frame of a prompt
        """
        self._last_emission_committed = False
        if self._reserved_emission_stopped:
            # Abandoned, but the rows are still withheld until the owner releases them.
            # Rendering upstream directly from here would write outside the transaction and
            # into a terminal that is still reserved. Compatibility rendering follows the
            # release: once the owner has unbound this bridge, upstream's own render is back
            # on the renderer and nothing routes through here at all.
            return

        if self._needs_resynchronization:
            self.resynchronize()
            if self._needs_resynchronization:
                # Recovery is waiting on the terminal to say where the cursor is. Drawing now
                # would guess at the origin, which is the thing recovery exists to avoid.
                return

        prepared = self.prepare(app, layout, is_done=is_done)
        if prepared is None:
            self._request_redraw()
            return
        if not self.commit(prepared):
            self._request_redraw()
            return
        self._last_emission_committed = True
        if self._frame_committed_handler is not None:
            self._frame_committed_handler()

    def _fire_after_render_through_bridge(self) -> None:
        """Tell the application a frame was rendered, but only if one actually was.

        A skipped frame -- recovery owed and unfinished, a preparation refused, a commit
        retired -- emitted nothing. Everything downstream of this event believes a frame is on
        the screen: layout metadata is published from it, and the command display treats it as
        the signal that its first frame has been drawn.
        """
        if not self._last_emission_committed:
            return
        self._after_render_original()

    def _request_cursor_position_through_bridge(self) -> None:
        """Let upstream ask for the cursor, and record the request if one went out.

        Upstream does not always emit one: in full-screen mode, and on backends that answer
        natively, it fills in the height and returns. Recording those would leave entries in
        the queue that no reply will ever consume, so what is recorded is what the renderer
        actually started waiting for.
        """
        renderer = self._renderer
        with self._lock.transaction("cursor position request"):
            if self._reserved_emission_stopped:
                return
            generations = self.generations()
            outstanding = len(renderer._waiting_for_cpr_futures)
            self._originals["request_absolute_cursor_position"]()
            if len(renderer._waiting_for_cpr_futures) > outstanding:
                self._pending_cpr.append(generations)

    def _report_cursor_row_through_bridge(self, row: int) -> None:
        """Take a reply upstream's key binding delivered, through the same validation.

        :param row: the one-based physical row the terminal reported
        """
        self.report_cursor_row(row)

    def _erase_through_bridge(self, leave_alternate_screen: bool = True) -> None:
        """Erase under the transaction, and treat what is left as unknown.

        An erase moves the cursor and clears the screen below it, so nothing may be diffed
        against what was there. Upstream's own ``reset()`` runs inside it, which is exactly the
        state the bridge must not inherit beliefs from.

        :param leave_alternate_screen: passed through to upstream
        """
        self._last_emission_committed = False
        with self._lock.transaction("erase"):
            try:
                self._originals["erase"](leave_alternate_screen)
                self._last_emission_committed = True
            finally:
                # Recorded whether or not it finished. An erase that raised part-way has still
                # moved the cursor and cleared some of what was below it, and a stream cannot
                # say how much.
                self.require_resynchronization("the renderer erased the screen")

    def _clear_through_bridge(self) -> None:
        """Clear under the transaction, and treat what is left as unknown.

        A clear also moves the prompt. Whatever row it started on, it is not that row now, so
        the remembered origin is forgotten rather than carried across -- recovery would
        otherwise place the next frame where the prompt used to be. Cursor reports already in
        flight describe the screen before the clear and are discarded with it.
        """
        self._last_emission_committed = False
        with self._lock.transaction("clear"):
            try:
                self._originals["clear"]()
                self._last_emission_committed = True
            finally:
                self._prompt_anchor = None
                self._invalidate_pending_cursor_reports()
                self.require_resynchronization("the renderer cleared the screen")

    # -- prepare and commit ----------------------------------------------------------------

    def prepare(self, app: "Application[Any]", layout: Any = None, *, is_done: bool = False) -> PreparedRender | None:
        """Record a full renderer frame without emitting anything.

        :param app: the application to render
        :param layout: the layout to render; the application's own by default
        :param is_done: whether this is the final frame of a prompt
        :return: the prepared frame, or ``None`` if one cannot be prepared right now
        """
        assert_no_terminal_transaction("preparing a renderer frame")
        if self._reserved_emission_stopped or self._needs_resynchronization or self._preparing or self._in_flight is not None:
            return None

        # One transaction, so a managed write or resize cannot land between reading the
        # terminal and recording which generation was read: facts and generations have to
        # describe the same terminal, or the batch is validated against one snapshot and
        # rendered from another.
        with self._lock.transaction("preflight"):
            facts = PreflightFacts.capture(self._display.output)
            generations = self.generations()

        recorder = RecordingOutput(facts)
        original = self._renderer.output
        self._renderer.output = recorder
        # Marked before the renderer is invoked, not after it returns. Layout, filter and
        # style callbacks run inside that call, and from the first of them the renderer's
        # state is provisional -- a second render or an input dispatch started from one of
        # them would consume a screen that does not exist.
        self._preparing = True
        render = self._originals.get("render", self._renderer.render)
        try:
            render(app, app.layout if layout is None else layout, is_done)
        except Exception as error:  # noqa: BLE001 - a layout callback must not end a command
            self._pending_error = error
            self.require_resynchronization("preparing the frame raised")
            return None
        finally:
            self._renderer.output = original
            self._preparing = False

        with self._lock.transaction("publish"):
            # Checking and publishing are one step. Apart, they are two, and a writer that
            # abandons the reservation between them has its retirement overwritten by the
            # publication that follows -- leaving a frame in flight that nothing invalidated
            # and everything downstream believes is current.
            if self.needs_resynchronization or self.reserved_emission_stopped:
                # Something invalidated the terminal while the frame was being prepared -- a
                # managed write from inside a layout callback, say, or a failure that
                # abandoned the reservation outright. Either way the operations are recorded
                # against a terminal that has moved on.
                self._retire()
                return None

            prepared = PreparedRender(batch=recorder.batch(), generations=generations)
            self._in_flight = prepared
            return prepared

    def commit(self, prepared: PreparedRender) -> bool:
        """Revalidate a prepared frame and, if it is still current, emit it.

        :param prepared: the frame to commit
        :return: whether the frame was emitted in full
        """
        assert_no_terminal_transaction("committing a prepared frame")
        with self._lock.transaction("commit", generation=prepared.generations.geometry):
            if prepared is not self._in_flight:
                # Already retired, or from a previous attempt. Replaying it would emit a frame
                # nothing has validated, and possibly emit it twice.
                #
                # Read here, after the terminal has been acquired: read before the wait, it
                # answers a question about a terminal somebody else still held, since a writer
                # can retire the batch while this call queues, changing neither the
                # generations nor the size.
                return False
            if self._needs_resynchronization or self._reserved_emission_stopped:
                # Not covered by the identity test above. Retirement clears the frame in
                # flight, but a preparation completing concurrently can publish a new one over
                # that retirement, and the frame it publishes matches on identity and on every
                # generation. What makes it uncommittable is the state of the terminal, so
                # that is what is asked.
                return False
            if self.generations() != prepared.generations:
                self.require_resynchronization("the terminal changed between preparing and committing")
                return False
            if prepared.batch.facts.size != self._display.output.get_size():
                # The generations can agree while the frame was laid out for a different
                # terminal -- the geometry is read once per snapshot, and the batch carries
                # what the renderer actually branched on. The frame's own facts are the last
                # word on whether it still fits.
                self.require_resynchronization("the frame was laid out for a different size")
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
            # Through the same door as every other abandonment, so the owner is told and can
            # give the rows back. Setting the flag here directly would stop emission while
            # leaving the reservation installed and the renderer bound -- and the later call
            # that would have notified now returns early, having found it already stopped.
            self.stop_reserved_emission(error)
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
        # Resolved before the terminal is taken: this runs application filters, which the
        # wait contract keeps off the lock.
        policy = self._desired_policy()

        with self._lock.transaction("resynchronize"):
            if self._reserved_emission_stopped:
                # Checked here rather than before the wait. Rendering can be abandoned while
                # this call queues for the terminal, and recovery would then write cursor and
                # mode sequences into a terminal nothing is allowed to emit to any more.
                raise ReservedModeFailureError("reserved emission has stopped; release before rendering again")
            # The origin is read *here*, not before the wait. Recovery can queue behind
            # another writer for as long as that writer holds the terminal, and what it does
            # in the meantime -- emitting output, moving the prompt, resizing -- is exactly
            # what changes where the prompt now starts. An origin read beforehand describes a
            # terminal somebody else still owned.
            origin = self._usable_prompt_anchor()
            if origin is None:
                can_report = self._display.output.responds_to_cpr
            else:
                self._establish(policy, origin)
                return

        if not can_report:
            raise ReservedModeFailureError("the prompt's origin is unknown and the terminal does not report its cursor")
        # The reply establishes the origin. Recovery stays owed until it arrives; guessing
        # would repaint the prompt over committed output.
        self.request_cursor_position()

    def _establish(self, policy: TerminalModePolicy, origin: int) -> None:
        """Put the terminal into the known state, from inside the transaction.

        Recovery is marked complete here rather than after the lock is given back: whoever
        takes the terminal next must not find a recovery still owed against work that has
        already been done.

        :param policy: the mode policy to establish
        :param origin: the physical row to place the cursor on
        """
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
        self._needs_resynchronization = False
        self._resynchronization_reason = None
        self._in_flight = None
        self._initialize_renderer(policy, origin)

    def _usable_rows(self) -> int:
        """How many rows the application may use right now.

        :return: the usable height
        """
        geometry = self._display.geometry
        if geometry is not None:
            return geometry.usable_rows
        return int(self._display.output.get_size().rows)

    def _usable_prompt_anchor(self) -> int | None:
        """Return the remembered prompt origin, if it is still inside the usable region.

        A remembered row survives a resize that the row does not: after the terminal shrinks,
        row 20 may be inside the reserved band or off the screen entirely. Rendering from
        there would put the prompt in the toolbar's rows, so an anchor that no longer fits is
        forgotten and re-established rather than trusted.

        :return: the anchor, or ``None`` if there is none or it is out of range
        """
        anchor = self._prompt_anchor
        if anchor is None:
            return None
        if not 1 <= anchor <= self._usable_rows():
            self._prompt_anchor = None
            return None
        return anchor

    def _desired_policy(self) -> TerminalModePolicy:
        """Evaluate the current owner's mode policy, off the terminal lock.

        :return: the policy to establish
        """
        return TerminalModePolicy(mouse_support=bool(self._renderer.mouse_support()))

    def _initialize_renderer(self, policy: TerminalModePolicy, origin: int) -> None:
        """Tell the renderer what the terminal now is.

        This is the version-specific half of recovery. Each assignment answers a field that
        upstream advances during rendering and never re-checks: the diff baseline and its size
        and style, the latched mode flags, the believed cursor position that a full repaint
        moves *from*, the mouse handlers a discarded frame published, and the available-height
        bookkeeping that a visible toolbar says nothing about.

        :param policy: the policy just established physically
        :param origin: the physical row the cursor was just placed on
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
        # Not zero. The cursor was just placed on a known row inside the usable region, so the
        # height below it is known by the same arithmetic a cursor-position reply would give:
        # zeroing it would leave the prompt's height unknown while input was allowed to
        # resume, which is the invalid state recovery exists to leave behind.
        renderer._min_available_height = self._usable_rows() - origin + 1

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
        with self._lock.transaction("cursor position request"):
            if self._reserved_emission_stopped:
                # Recovery gives the terminal back before asking for it again to send this
                # request, so emission can be abandoned in between. Checked here for the same
                # reason recovery checks it here: before the wait, the answer describes a
                # terminal somebody else still held.
                return False
            # Recorded here, not before the wait. A managed write can land while this call
            # queues for the terminal, and a request stamped with the generations from before
            # that write would have its own reply rejected as stale.
            #
            # The whole generation tuple, not just the geometry: the terminal samples the
            # cursor when it processes the request, so output written afterwards moves the
            # very thing the reply describes.
            generations = self.generations()
            output.ask_for_cpr()
            output.flush()
            self._pending_cpr.append(generations)
        return True

    def report_cursor_row(self, row: int) -> bool:
        """Take a cursor-position reply, in physical coordinates.

        Replies carry no generation on the wire, so they are correlated by order against the
        requests this bridge made. A reply from before a geometry change describes a screen
        that no longer exists and must not satisfy the request made after it. Requests whose
        screen has since been cleared away are kept in the queue but marked: their replies are
        still coming and still have to be consumed in order, and none of them can be believed.

        A reply is stale when anything about the terminal has changed since the request went
        out -- a resize, an owner change, or managed output that moved the cursor the terminal
        was about to sample.

        A row inside the reserved band is the failure named in the design: upstream would
        compute ``U - r + 1``, which is zero at the first reserved row and negative below it,
        and would leave the prompt's height silently invalid rather than raising.

        Validating the reply and publishing the origin it establishes happen in one terminal
        transaction. Split, they are two steps a managed write can land between: the reply
        passes as current, the write moves the prompt, and the anchor it just recorded is then
        overwritten by a row that is no longer where the prompt is. Managed output reaches the
        terminal inside this same lock, so a reply validated here cannot be overtaken by one.

        Completing the renderer's own pending report only schedules its callbacks on the event
        loop, which is not a wait and dispatches no application code, so it belongs inside the
        transaction with the decision it settles.

        :param row: the one-based physical row the terminal reported
        :return: whether the reply was accepted and used
        """
        with self._lock.transaction("cursor position report"):
            if not self._pending_cpr:
                # Nothing outstanding: a late reply from a stream that was already drained. It
                # must not be allowed to answer a request that was never made.
                self._settle_renderer_cpr()
                return False
            # Popped whatever the outcome: replies correlate by order, so dropping one without
            # taking it off the queue would answer every later request with its predecessor.
            generations = self._pending_cpr.popleft()
            if generations is None or generations != self.generations():
                self._settle_renderer_cpr()
                return False

            usable = self._usable_rows()
            if not 1 <= row <= usable:
                self._settle_renderer_cpr()
                self.require_resynchronization(f"cursor position report row {row} is inside the reserved band")
                return False

            self._prompt_anchor = row
            report = self._originals.get("report_absolute_cursor_row", self._renderer.report_absolute_cursor_row)
            report(row)
            return True

    def _invalidate_pending_cursor_reports(self) -> None:
        """Mark every outstanding request unbelievable, without forgetting that it is coming.

        Used where the screen changed underneath the requests themselves. Emptying the queue
        would not stop the replies: they are already in the terminal's hands, and the next one
        to arrive would be matched against whatever request came *after* the change -- the
        oldest reply answering the newest question. The entries stay, marked, so each reply is
        still consumed in order and each one is refused.
        """
        self._pending_cpr = deque([None] * len(self._pending_cpr))

    def _settle_renderer_cpr(self) -> None:
        """Resolve one of the renderer's own pending reports, if it has any.

        A rejected reply still has to settle the bookkeeping it would have settled. Left
        pending, the renderer waits for a report that is never coming.
        """
        futures = self._renderer._waiting_for_cpr_futures
        if futures:
            futures.popleft().set_result(None)
