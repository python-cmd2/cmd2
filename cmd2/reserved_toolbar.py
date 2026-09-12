"""Own the reservation, the bridge and the painter for one command loop.

This is the seam between cmd2's lifecycle and the reserved-row machinery. Everything it does
is a pair: acquire and release, bind and restore, build and drop. The pairing matters more
than the individual halves -- a reservation left installed makes every later line of shell
output scroll inside a region the shell knows nothing about, and a backend left wrapped
reports a terminal one row shorter than it is to whatever runs next.

Binding is two assignments, not one. ``Application.output`` is what the application and its
session report, but the renderer keeps its *own* reference to the output it was constructed
with, so binding only the application leaves the renderer drawing through the unwrapped
backend -- straight over the reserved row. Both are restored on the way out, and only if they
still hold what this object put there: something else may have replaced them in between, and
putting a stale object back would be worse than leaving the newer one alone.

The toolbar's content is read through a callable rather than captured, so a caller assigning a
new ``bottom_toolbar`` to the session still reaches the band.
"""

import os
import signal
from contextlib import ExitStack, contextmanager, suppress
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.filters import Condition, Never
from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.styles import DynamicStyle
from prompt_toolkit.utils import suspend_to_background_supported

from .prompt_toolkit_bridge import PromptToolkitBridge
from .reserved_output import ReservedOutput
from .terminal_display import TerminalDisplay
from .terminal_transaction import TerminalLock
from .theme import get_pt_theme
from .toolbar_painter import ToolbarPainter

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Iterator

    from prompt_toolkit.formatted_text import AnyFormattedText
    from prompt_toolkit.shortcuts import PromptSession


#: Consecutive failed paints before the reservation is given up. One is a bad moment -- a
#: window resize mid-write, a transient device error. Two in a row is a terminal that is not
#: coming back, and holding rows in it helps nobody.
_MAX_CONSECUTIVE_PAINT_FAILURES = 2


def native_toolbar_container(session: "PromptSession[Any]") -> ConditionalContainer | None:
    """Find the window prompt-toolkit draws the bottom toolbar in.

    The shape is checked explicitly rather than assumed: ``PromptSession`` offers no public
    hook for its toolbar window, so this is a dependency on its layout that has to fail
    visibly when upstream changes it -- not quietly suppress the wrong container.

    :param session: the prompt session to look in
    :return: the toolbar's container, or ``None`` if this layout has no recognizable one
    """
    root = session.app.layout.container
    if not isinstance(root, HSplit) or not root.children:
        return None
    candidate = root.children[-1]
    if (
        isinstance(candidate, ConditionalContainer)
        and isinstance(candidate.content, Window)
        and candidate.content.style == "class:bottom-toolbar"
    ):
        return candidate
    return None


class ReservedToolbar:
    """The reserved-row toolbar's lifetime, tied to one prompt session."""

    def __init__(
        self,
        session: "PromptSession[Any]",
        content: "Callable[[], AnyFormattedText]",
        reserved_rows: int = 1,
    ) -> None:
        """Prepare a reservation for a session's terminal.

        Nothing is acquired or bound until :meth:`start`; a session that never enters its
        command loop must leave the terminal exactly as it found it.

        :param session: the main prompt session whose terminal is reserved
        :param content: called to obtain the toolbar's formatted text
        :param reserved_rows: rows to withhold at the bottom of the screen
        """
        self._session = session
        self.content = content
        self._reserved_rows = reserved_rows
        self._display: TerminalDisplay | None = None
        self._bridge: PromptToolkitBridge | None = None
        self._painter: ToolbarPainter | None = None
        self._lock = TerminalLock()
        self._bound_output: Any = None
        # The application's output and the renderer's are saved separately. They are usually
        # the same object, but nothing guarantees it, and restoring one over the other would
        # hand the renderer a terminal it never had.
        self._original_app_output: Any = None
        self._original_renderer_output: Any = None
        self._pending_error: BaseException | None = None
        self._suspend_depth = 0
        self._consecutive_paint_failures = 0
        self._native_toolbar: ConditionalContainer | None = None
        self._original_filter: Any = None
        self._installed_filter: Any = None
        self.stopped_handler: Callable[[], None] | None = None
        self._job_control_stack = ExitStack()
        self._nested_stacks: list[ExitStack] = []
        self._nested_bridges: list[PromptToolkitBridge] = []

    @property
    def is_active(self) -> bool:
        """Whether rows are reserved right now and the band is this object's to paint.

        Owning the display is not the same as holding a region. A terminal below the two-row
        floor, or one on loan to a guest program, leaves this object in charge of the
        reservation *and* leaves no reservation installed -- and while there is no band, the
        native toolbar is what has to render.
        """
        return self._display is not None and self._display.is_reserved

    @property
    def display(self) -> TerminalDisplay:
        """The display owning the reservation.

        :raises RuntimeError: if no reservation is held
        """
        if self._display is None:
            raise RuntimeError("the reserved toolbar is not started")
        return self._display

    @property
    def bridge(self) -> PromptToolkitBridge | None:
        """The renderer bridge while active, else ``None``."""
        return self._nested_bridges[-1] if self._nested_bridges else self._bridge

    @property
    def painter(self) -> ToolbarPainter | None:
        """The band painter while active, else ``None``."""
        return self._painter

    @property
    def lock(self) -> TerminalLock:
        """The terminal transaction lock every cmd2-controlled writer shares."""
        return self._lock

    def start(self) -> bool:
        """Acquire the reservation and bind the application to it.

        A terminal too short for the floor keeps its lease and resize bridge. The adapter
        exposes the full terminal until growth makes a reservation possible.

        :return: whether a reservation was installed
        """
        if self._display is not None:
            return self.is_active

        app = self._session.app
        native = native_toolbar_container(self._session)
        if native is None:
            # Selection is supposed to have established this already. Reaching here means the
            # layout changed underneath us, and reserving rows while the native toolbar still
            # draws would put two toolbars on the screen.
            raise RuntimeError("cannot locate the session's bottom toolbar window")

        display = TerminalDisplay(app.output, reserved_rows=self._reserved_rows)
        if not display.terminal.supports_reservation:
            # Mode selection refuses an unqualified backend before this runs, so this is for
            # a caller using the class directly. Nothing is bound: a terminal below the floor
            # keeps a lease and a bridge for the resize that may make a reservation possible,
            # but an unqualified backend can never reserve, whatever its size.
            return False
        display.acquire()

        self._display = display
        try:
            self._original_app_output = app.output
            self._original_renderer_output = app.renderer.output
            # Keep a live view even if startup is below the height floor. Binding the raw
            # backend there would leave Application.output unadapted after reacquisition.
            self._bound_output = display.output if display.is_reserved else ReservedOutput(app.output, display)
            app.output = self._bound_output
            app.renderer.output = self._bound_output

            # Hidden by asking whether the reservation is live rather than by latching a
            # False. A restoration that never runs -- a teardown that raised, a caller that
            # dropped this object -- then leaves a filter that heals itself instead of a
            # toolbar that is gone for the rest of the session.
            self._native_toolbar = native
            self._original_filter = native.filter
            self._installed_filter = native.filter & Condition(lambda: not self.is_active)
            native.filter = self._installed_filter

            self._bridge = PromptToolkitBridge(renderer=app.renderer, display=display, lock=self._lock)
            # From here the application's own renders go through prepare and commit, which is
            # what puts them in the same queue as command output and toolbar paints.
            self._bridge.bind(app)
            self._job_control_stack.enter_context(self._job_control(app))
            # When the bridge abandons reserved rendering it cannot resume anything itself:
            # the rows are still withheld and the renderer is still routed through it. Giving
            # them back is this object's job, and it is what lets compatibility rendering
            # start.
            self._bridge.set_emission_stopped_handler(self._emission_stopped)
            # The band is repainted after each frame the terminal actually received. That ties
            # it to the refresh cadence the session already has -- its refresh interval, its
            # invalidations, its key presses -- rather than inventing a second timer, and it
            # paints after the prompt rather than into the middle of it.
            self._bridge.set_frame_committed_handler(self.refresh)
            self._painter = ToolbarPainter(
                display=display,
                lock=self._lock,
                style=DynamicStyle(get_pt_theme),
                color_depth=app.color_depth,
                default_style="class:bottom-toolbar",
            )
            # Strict on the way in: a band that cannot be painted at all is a reservation
            # that cannot be established, and the rollback below hands the terminal back
            # rather than leaving the caller with rows nothing can draw in. Once established,
            # the same failure is survivable -- see :meth:`refresh`.
            self._paint_once()
        except BaseException:
            # Everything after the acquisition has to come back off. A caller using this as a
            # context manager never reaches ``__exit__`` when ``__enter__`` raises, so a
            # failure here would otherwise leave the margins installed, both outputs wrapped
            # and the native toolbar suppressed -- a terminal nobody owns and nobody will
            # release. Cleanup is best-effort: if it fails too, the original failure is the
            # one worth propagating.
            with suppress(Exception):
                self.stop()
            raise
        return self.is_active

    def take_pending_error(self) -> BaseException | None:
        """Take the failure waiting to be reported, if there is one.

        :return: the error to report once, or ``None``
        """
        error, self._pending_error = self._pending_error, None
        if error is None and self._painter is not None:
            error = self._painter.take_pending_error()
        return error

    @contextmanager
    def _job_control(self, app: Any) -> "Iterator[None]":
        """Release the physical reservation inside upstream's cooked-mode handoff."""
        original = app.suspend_to_background

        def suspend_to_background(suspend_group: bool = True) -> None:
            if not suspend_to_background_supported():
                return

            def suspend_process() -> None:
                # run_in_terminal has stopped rendering and detached input before this runs.
                # A signal callback itself must never acquire the terminal transaction.
                with self.suspended():
                    os.kill(0 if suspend_group else os.getpid(), signal.SIGTSTP)

            run_in_terminal(suspend_process)

        app.suspend_to_background = suspend_to_background
        try:
            yield
        finally:
            if app.suspend_to_background is suspend_to_background:
                app.suspend_to_background = original

    def can_manage(self, session: "PromptSession[Any]") -> bool:
        """Whether a temporary prompt uses this terminal and its managed input reader."""
        return (
            self._display is not None
            and not self._display.handoff_active
            and session.input is self._session.input
            and session.app.output in (self._bound_output, self._display.terminal.output)
            and native_toolbar_container(session) is not None
        )

    @contextmanager
    def prompt_session(self, session: "PromptSession[Any]") -> "Iterator[None]":
        """Lend the reservation to a temporary prompt after the command reader has stopped."""
        if session is self._session:
            yield
            return
        native = native_toolbar_container(session)
        if native is None:
            raise RuntimeError("cannot locate the nested session's bottom toolbar window")
        with self.prompt_application(session.app, native):
            yield

    @contextmanager
    def prompt_application(self, app: Any, native: ConditionalContainer | None = None) -> "Iterator[None]":
        """Bind a managed input application while retaining the physical reservation."""
        previous_output, previous_renderer_output = app.output, app.renderer.output
        previous_filter = native.filter if native is not None else Never()
        output = self._bound_output
        installed_filter = previous_filter & Condition(lambda: not self.is_active)
        bridge = PromptToolkitBridge(renderer=app.renderer, display=self.display, lock=self._lock)
        previous_bridge = self.bridge
        if previous_bridge is not None:
            previous_bridge.forget_prompt_anchor()
            previous_bridge.note_owner_change()

        def restore() -> None:
            bridge.unbind()
            if bridge in self._nested_bridges:
                self._nested_bridges.remove(bridge)
            if app.output is output:
                app.output = previous_output
            if app.renderer.output is output:
                app.renderer.output = previous_renderer_output
            if native is not None and native.filter is installed_filter:
                native.filter = previous_filter
            if previous_bridge is not None:
                previous_bridge.forget_prompt_anchor()
                previous_bridge.require_resynchronization("a nested prompt returned the terminal")

        with ExitStack() as stack:
            stack.callback(restore)
            # Abandonment restores the guest immediately, before native rendering resumes.
            self._nested_stacks.append(stack)
            stack.callback(self._nested_stacks.remove, stack)
            app.output = app.renderer.output = output
            if native is not None:
                native.filter = installed_filter
            self._nested_bridges.append(bridge)
            bridge.bind(app)
            bridge.set_frame_committed_handler(self.refresh)
            bridge.set_emission_stopped_handler(self._emission_stopped)
            stack.enter_context(self._job_control(app))
            yield

    @contextmanager
    def suspended(self, *, defer_band_clear: bool = False) -> "Iterator[None]":
        """Give the rows back for the duration of the block, and take them again after.

        A program that inherits the terminal -- a shell command, an editor, an external pager
        -- knows nothing about a scroll region, and one left installed would confine its
        output to rows it never asked for. The lease is kept: this is a loan, not a release,
        and the geometry is measured afresh on the way back because the guest may have resized
        the window.

        What the guest left on the screen is unknown, so the band's contents and the
        renderer's beliefs are both discarded rather than trusted.

        A terminal with no region installed -- one below the two-row floor -- still goes
        through this. There is nothing to give back, but the guest may resize the window, and
        the return path is where that is noticed and the rows are taken again.

        Suspensions nest, and only the outermost one changes anything. cmd2 suspends around
        its own external commands and callers suspend around theirs, so an inner block ending
        says nothing about whose terminal it is: the guest the outer block handed it to still
        has it, and reinstalling margins or painting a band over their screen would be the
        same mistake as never releasing at all.

        :param defer_band_clear: keep the main-screen bar visible during managed pager
            preparation; external terminal users must retain the default immediate clear.
        """
        display = self._display
        if display is None:
            yield
            return

        outermost = self._suspend_depth == 0 and not display.handoff_active
        self._suspend_depth += 1
        body_failed = False
        try:
            if not defer_band_clear:
                with self._lock.transaction("clear retained toolbar"):
                    display.clear_deferred_band()
            if outermost:
                with self._lock.transaction("suspend"):
                    display.release_region_for_handoff(defer_band_clear=defer_band_clear)
                    # Forgotten as the terminal changes hands, not after the guest has
                    # finished with it. From this moment the remembered row describes a screen
                    # someone else is writing on, and anything that rendered against it would
                    # paint over their output.
                    self._invalidate_ownership("the terminal was handed to another program")
            yield
        except BaseException:
            body_failed = True
            raise
        finally:
            self._suspend_depth -= 1
            if outermost:
                try:
                    with self._lock.transaction("resume"):
                        display.reacquire_region_after_handoff()
                        self._invalidate_ownership("the terminal came back from another program")
                    self.refresh()
                except Exception as error:
                    self._pending_error = error
                    with suppress(Exception):
                        self.stop()
                    # A failed guest (including Ctrl-C/termination) remains the reason for
                    # unwinding; cleanup failure is available through take_pending_error().
                    if not body_failed:
                        raise

    def _invalidate_ownership(self, reason: str) -> None:
        """Discard everything that described the screen before ownership changed.

        :param reason: why, for diagnostics
        """
        if self._painter is not None:
            self._painter.invalidate()
        if self._bridge is not None:
            self._bridge.forget_prompt_anchor()
            self._bridge.forget_unfinished_command_output()
            self._bridge.require_resynchronization(reason)
        for bridge in self._nested_bridges:
            bridge.forget_prompt_anchor()
            bridge.require_resynchronization(reason)

    def refresh(self) -> bool:
        """Evaluate the toolbar's content and paint whatever changed.

        A failure here never reaches the command that was running. The toolbar is cosmetic and
        the command is not its to interrupt, so the error is kept for the caller to report and
        the terminal is put back into a state the next frame can trust.

        :return: whether anything was written
        """
        try:
            painted = self._paint_once()
        except Exception as error:  # noqa: BLE001 - a failed paint must not end a command
            self._paint_failed(error)
            return False
        self._consecutive_paint_failures = 0
        return painted

    def _paint_once(self) -> bool:
        """Evaluate the content and paint it, letting any failure out.

        :return: whether anything was written
        """
        painter = self._painter
        if painter is None:
            return False
        prepared = painter.prepare(self.content)
        if prepared is None:
            return False
        return painter.paint(prepared)

    def _emission_stopped(self) -> None:
        """Release the reservation after the bridge has given up on it.

        The error the bridge is holding is taken here rather than left with it: the bridge is
        dropped a moment later, and an error the user never sees is the same as none.
        """
        if self.bridge is not None and self._pending_error is None:
            self._pending_error = self.bridge.take_pending_error()
        with suppress(Exception):
            self.stop()

    def _paint_failed(self, error: BaseException) -> None:
        """Record a failed paint and decide whether the reservation can continue.

        The backend clears its buffer before writing it, so a failed flush cannot say whether
        the terminal received a prefix of the batch or none of it. Either way the cursor is
        somewhere this process no longer knows, which makes it the renderer's problem as much
        as the painter's: the next frame would be drawn from a believed position that may not
        be where the cursor is. Recovery is therefore owed before anything renders again.

        One failure is a bad moment; two in a row is a terminal that has gone away. The second
        gives the rows back and lets the native toolbar render again, because compatibility
        rendering starts only after the reservation has been released -- never alongside it.

        :param error: what the paint raised
        """
        self._pending_error = error
        self._consecutive_paint_failures += 1
        if self.bridge is not None:
            self.bridge.require_resynchronization("a toolbar paint failed; the cursor's position is unknown")
        if self._consecutive_paint_failures >= _MAX_CONSECUTIVE_PAINT_FAILURES:
            with suppress(Exception):
                self.stop()

    def stop(self) -> None:
        """Restore the application's bindings and release the reservation.

        Safe to call when nothing was started and safe to call twice: teardown reaches this
        from the loop's ``finally`` and from explicit shutdown, and neither knows about the
        other.
        """
        display, self._display = self._display, None
        for stack in reversed(tuple(self._nested_stacks)):
            stack.close()
        self._job_control_stack.close()
        if self._bridge is not None:
            self._bridge.unbind()
        self._bridge = None
        # The painter is dropped, so anything it was holding to report goes with it unless it
        # is taken now. An error the user never sees is the same as no error handling at all.
        if self._painter is not None and self._pending_error is None:
            self._pending_error = self._painter.take_pending_error()
        self._painter = None
        self._consecutive_paint_failures = 0
        if display is None:
            return

        # Everything here restores only what is still ours. Something else may have replaced
        # any of it while the reservation was live, and putting a stale object back is worse
        # than leaving a newer one alone.
        native, self._native_toolbar = self._native_toolbar, None
        if native is not None and native.filter is self._installed_filter:
            native.filter = self._original_filter
        self._original_filter = None
        self._installed_filter = None

        app = self._session.app
        if app.output is self._bound_output:
            app.output = self._original_app_output
        if app.renderer.output is self._bound_output:
            app.renderer.output = self._original_renderer_output
        self._bound_output = None
        self._original_app_output = None
        self._original_renderer_output = None
        display.release()
        if self.stopped_handler is not None:
            self.stopped_handler()

    def __enter__(self) -> Self:
        """Start the reservation."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the reservation, including when the body raised."""
        self.stop()
