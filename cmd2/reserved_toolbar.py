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

from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

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
        self._original_output: Any = None

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
        display = TerminalDisplay(app.output, reserved_rows=self._reserved_rows)
        if not display.acquire():
            # Nothing was installed, so there is nothing to release; leaving the lease held
            # would make every later acquire a no-op at depth two.
            display.release()
            return False

        self._display = display
        self._original_output = app.output
        self._bound_output = display.output
        app.output = self._bound_output
        app.renderer.output = self._bound_output

        self._bridge = PromptToolkitBridge(renderer=app.renderer, display=display, lock=self._lock)
        self._painter = ToolbarPainter(
            display=display,
            lock=self._lock,
            style=DynamicStyle(get_pt_theme),
            color_depth=app.color_depth,
            default_style="class:bottom-toolbar",
        )
        return True

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

        app = self._session.app
        # Only put the original back where the adapter is still installed. Something else may
        # have rebound these in between, and a stale object is worse than a newer one.
        if app.output is self._bound_output:
            app.output = self._original_output
        if app.renderer.output is self._bound_output:
            app.renderer.output = self._original_output
        self._bound_output = None
        self._original_output = None
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
