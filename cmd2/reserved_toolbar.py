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

from contextlib import suppress
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.styles import DynamicStyle

from .prompt_toolkit_bridge import PromptToolkitBridge
from .terminal_display import TerminalDisplay
from .terminal_transaction import TerminalLock
from .theme import get_pt_theme
from .toolbar_painter import ToolbarPainter

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from prompt_toolkit.formatted_text import AnyFormattedText
    from prompt_toolkit.shortcuts import PromptSession


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
        self._native_toolbar: ConditionalContainer | None = None
        self._original_filter: Any = None
        self._installed_filter: Any = None

    @property
    def is_active(self) -> bool:
        """Whether a reservation is installed and the application is bound to it."""
        return self._display is not None

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
        return self._bridge

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

        A terminal too short for the floor is not an error: the lease is simply refused, and
        the application keeps rendering through its own backend exactly as it did before.

        :return: whether a reservation was installed
        """
        if self._display is not None:
            return True

        app = self._session.app
        native = native_toolbar_container(self._session)
        if native is None:
            # Selection is supposed to have established this already. Reaching here means the
            # layout changed underneath us, and reserving rows while the native toolbar still
            # draws would put two toolbars on the screen.
            raise RuntimeError("cannot locate the session's bottom toolbar window")

        display = TerminalDisplay(app.output, reserved_rows=self._reserved_rows)
        if not display.acquire():
            # Nothing was installed, so there is nothing to release; leaving the lease held
            # would make every later acquire a no-op at depth two.
            display.release()
            return False

        self._display = display
        try:
            self._original_app_output = app.output
            self._original_renderer_output = app.renderer.output
            self._bound_output = display.output
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
            self._painter = ToolbarPainter(
                display=display,
                lock=self._lock,
                style=DynamicStyle(get_pt_theme),
                color_depth=app.color_depth,
                default_style="class:bottom-toolbar",
            )
            self.refresh()
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
        return True

    def refresh(self) -> bool:
        """Evaluate the toolbar's content and paint whatever changed.

        :return: whether anything was written
        """
        painter = self._painter
        if painter is None:
            return False
        prepared = painter.prepare(self.content)
        if prepared is None:
            return False
        return painter.paint(prepared)

    def stop(self) -> None:
        """Restore the application's bindings and release the reservation.

        Safe to call when nothing was started and safe to call twice: teardown reaches this
        from the loop's ``finally`` and from explicit shutdown, and neither knows about the
        other.
        """
        display, self._display = self._display, None
        self._bridge = None
        self._painter = None
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
