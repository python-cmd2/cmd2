"""Internal support for displaying a toolbar during synchronous commands."""

import codecs
import contextlib
import contextvars
import functools
import os
import signal
import sys
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TYPE_CHECKING, Any, TextIO, TypeVar, cast

from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.filters import Condition, to_filter
from prompt_toolkit.input.typeahead import get_typeahead, store_typeahead
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPress, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.patch_stdout import StdoutProxy
from prompt_toolkit.utils import suspend_to_background_supported

from .managed_output import SerializedTerminalWriter
from .pager import Pager, output_fits

if TYPE_CHECKING:
    from .cmd2 import Cmd

#: How long to wait for the display to report that it has started. Long enough that a busy
#: machine is not mistaken for a broken one, short enough that a command is never held forever.
_STARTUP_TIMEOUT = 10.0

#: How long to wait for the display's thread to finish. Bounded for the same reason: a render
#: callback blocked inside it would otherwise hold whoever is tearing the display down.
_SHUTDOWN_TIMEOUT = 10.0

_F = TypeVar("_F", bound=Callable[..., Any])
_R = TypeVar("_R")


def suspend_toolbar(func: _F) -> _F:
    """Give a method exclusive access to the terminal, reserved rows included.

    For methods that hand the terminal to something else: a shell command, an editor, an
    embedded interpreter, an external pager. Anything that does not know about a scroll region
    must not be given one.
    """

    @functools.wraps(func)
    def wrapped(self: "Cmd", *args: Any, **kwargs: Any) -> Any:
        with self.suspend_bottom_toolbar():
            return func(self, *args, **kwargs)

    return cast(_F, wrapped)


def quiesce_toolbar(func: _F) -> _F:
    """Stop the command display for a method without giving the terminal away.

    For methods that need the renderer and the input reader quiet but are still part of the
    command loop -- command finalization above all, which restores terminal input settings at
    the end of every command and must leave the toolbar exactly where it was.
    """

    @functools.wraps(func)
    def wrapped(self: "Cmd", *args: Any, **kwargs: Any) -> Any:
        with self._quiesce_bottom_toolbar():
            return func(self, *args, **kwargs)

    return cast(_F, wrapped)


def pipe_target(stream: Any) -> Any:
    """Return the stream a pipe process can inherit, or ``None`` if its output must be captured.

    A pipe process may be interactive, such as ``less`` or ``fzf``, so it needs the real
    terminal rather than a stream this process reads on its behalf. Look through a
    :class:`ToolbarStream` wrapper, but only hand back a stream owning a file descriptor.
    """
    if isinstance(stream, ToolbarStream):
        stream = stream.original
    try:
        stream.fileno()
    except (AttributeError, OSError):
        # io.UnsupportedOperation, raised by streams like io.StringIO, subclasses OSError.
        return None
    return stream


class _DisplayStillRunningError(RuntimeError):
    """Raised when the display's thread did not finish within its timeout.

    Nothing was relinquished: the thread is still inside the application, so whatever was
    about to be done with the terminal must not be.
    """


class _ContextStdoutProxy(StdoutProxy):
    """Keep stdout's flush worker in the toolbar's isolated application session."""

    def _start_write_thread(self) -> threading.Thread:
        context = contextvars.copy_context()
        thread = threading.Thread(target=context.run, args=(self._write_thread,), daemon=True)
        thread.start()
        return thread


class ToolbarStream:
    """Keep a stable stream identity across suspensions and cmd2 redirections.

    Output has three possible destinations, in priority order. A *serializer* is installed in
    reserved mode: the toolbar sits in rows withheld from scrolling, so output goes straight
    to the terminal under the terminal transaction rather than through a proxy that erases the
    toolbar and draws it again. A *proxy* is prompt-toolkit's, used in legacy rendering to put
    output above a toolbar that does scroll. With neither, the terminal stream itself -- which
    is what a suspended toolbar leaves behind.
    """

    def __init__(self, original: TextIO, lock: "threading.RLock") -> None:
        """Wrap a terminal stream while preserving its ordinary file attributes."""
        self.original = original
        self.proxy: StdoutProxy | None = None
        self.serializer: SerializedTerminalWriter | None = None
        # Shared with the toolbar so a write from another thread cannot land on a proxy
        # that is being closed. Such a write is accepted by the dead proxy and discarded.
        self._lock = lock
        self.buffer = _ToolbarBuffer(self)

    def write(self, data: str) -> int:
        """Write above the toolbar, or directly while the toolbar is suspended."""
        with self._lock:
            serializer = self.serializer
            if serializer is None:
                return (self.proxy or self.original).write(data)
        # Chosen and performed in one acquisition, or performed after a single one. Deciding
        # under the lock, releasing it, and then taking it again to act would let the
        # destination change in between -- a serializer installed in that gap would be
        # skipped, and its write would reach the terminal outside any transaction.
        #
        # The serializer runs after the release because it takes the terminal lock, which is
        # the last lock in the output path: carrying a routing lock into it is the deadlock
        # the ordering rule exists to prevent.
        return serializer.write(data)

    def flush(self) -> None:
        """Flush the currently active output stream."""
        with self._lock:
            serializer = self.serializer
            if serializer is None:
                (self.proxy or self.original).flush()
                return
        serializer.flush()

    def __getattr__(self, name: str) -> Any:
        """Delegate file attributes to the original terminal stream."""
        return getattr(self.original, name)


class _ToolbarBuffer:
    """Decode subprocess output incrementally, including split Unicode characters."""

    def __init__(self, stream: ToolbarStream) -> None:
        self.stream = stream
        self._decoder = codecs.getincrementaldecoder(stream.original.encoding or "utf-8")(errors="replace")
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        with self._lock:
            self.stream.write(self._decoder.decode(data))
        return len(data)

    def flush(self) -> None:
        self.stream.flush()

    def finish(self) -> None:
        with self._lock:
            self.stream.write(self._decoder.decode(b"", final=True))
            self._decoder.reset()


class CommandToolbar:
    """Borrow the main prompt's application while a command runs on the main thread.

    The display owns terminal input so it can receive cursor position reports. Keys
    typed during execution are saved for the next prompt; Ctrl-C is sent to cmd2's
    normal signal handler. Terminal output goes through prompt-toolkit's stdout
    proxy so that it appears above the toolbar.
    """

    def __init__(self, cmd: "Cmd") -> None:
        """Configure a command display using the main prompt's terminal and settings."""
        self.cmd = cmd
        self._stack: contextlib.ExitStack | None = None
        self._keys: list[KeyPress] = []
        self._error: BaseException | None = None
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._streams: list[ToolbarStream] = []
        self._proxy: StdoutProxy | None = None
        self._serialized = False
        self._lock = threading.RLock()
        self._pausing = False

        session = cmd.main_session
        self.app = session.app
        # PromptSession has no public hook for replacing just its input area.
        # Keep this small dependency on its layout shape in one place, and fail
        # explicitly if upstream changes it. Reuse the actual toolbar container,
        # including its visibility filter and support for multiline toolbars.
        root = session.layout.container
        if not isinstance(root, HSplit):
            raise TypeError("Unsupported PromptSession layout")
        self.toolbar = root.children[-1]
        if not (
            isinstance(self.toolbar, ConditionalContainer)
            and isinstance(self.toolbar.content, Window)
            and self.toolbar.content.style == "class:bottom-toolbar"
        ):
            raise RuntimeError("Cannot locate PromptSession bottom toolbar")
        self._layout = Layout(HSplit([Window(height=0), Window(), self.toolbar]))
        self._display_stack: contextlib.ExitStack | None = None
        bindings = KeyBindings()

        @bindings.add("<any>")
        def save_key(event: KeyPressEvent) -> None:
            self._keys.extend(event.key_sequence)

        @bindings.add("c-c")
        def interrupt(event: KeyPressEvent) -> None:  # noqa: ARG001
            # Match the terminal's normal Ctrl-C input flush: cancelled typeahead
            # must not become a command when the main prompt resumes.
            self._keys.clear()
            if sys.platform == "win32":
                # os.kill(..., SIGINT) terminates the process on Windows instead
                # of dispatching Python's signal handler. This reaches only this
                # process, so a console subprocess started by a command keeps
                # running until it is waited on.
                import _thread

                _thread.interrupt_main()
            else:
                # Raw mode clears ISIG, so no signal is generated for us. Signal the
                # foreground process group the way the terminal driver would, since a
                # command may be waiting on a subprocess that shares this group. Pipe
                # processes are excluded because cmd2 starts them in their own session
                # and forwards to them from sigint_handler().
                os.killpg(os.getpgrp(), signal.SIGINT)

        @bindings.add(
            "c-z",
            filter=Condition(lambda: suspend_to_background_supported() and to_filter(session.enable_suspend)()),
        )
        def suspend(event: KeyPressEvent) -> None:
            # This restores cooked mode before stopping the process group and
            # redraws the toolbar after the process resumes.
            event.app.suspend_to_background()

        self._bindings = bindings
        self._suspend_binding = suspend

    def _display_started(self, app: Application[str]) -> None:  # noqa: ARG002
        """Report that the display is up and has finished its first frame."""
        self._ready.set()

    def _display_started_without_app(self) -> None:
        """Report readiness from a render attempt that produced no frame.

        A skipped frame still means the application is running and rendering. Waiting for one
        that commits would make starting the display depend on a cursor-position round trip,
        and a terminal that never answers would never let the command begin.
        """
        self._ready.set()

    def _reserved_bridge(self) -> Any:
        """Return the renderer bridge, when a reservation is holding the toolbar.

        :return: the bridge, or ``None`` in legacy rendering
        """
        reserved = self.cmd.reserved_toolbar
        if reserved is None or not reserved.is_active:
            return None
        return reserved.bridge

    def start(self) -> None:
        """Start rendering and protect terminal output."""
        stack = contextlib.ExitStack()
        self._stack = stack
        self._ready.clear()
        self._error = None
        try:
            stack.enter_context(create_app_session(input=self.app.input, output=self.app.output))
            # Only replace terminal streams. In particular, preserve redirected stderr
            # and self.stdout when a nested command has redirected its output to a file.
            for obj, name in ((self.cmd, "stdout"), (sys, "stdout"), (sys, "stderr")):
                stream = getattr(obj, name)
                if stream.isatty():
                    wrapper = ToolbarStream(stream, self._lock)
                    self._streams.append(wrapper)
                    setattr(obj, name, cast(TextIO, wrapper))
                    stack.callback(self._restore_stream, obj, name, wrapper)
            self._resume()
        except BaseException:
            # A cleanup that cannot finish is reported by the state it leaves behind -- the
            # display is disabled for the session either way -- and the failure that brought
            # us here is the one worth propagating.
            with contextlib.suppress(Exception):
                self.stop()
            raise

    @staticmethod
    def _restore_stream(obj: Any, name: str, stream: ToolbarStream) -> None:
        if getattr(obj, name) is stream:
            setattr(obj, name, stream.original)

    def _resume(self) -> None:
        self._ready.clear()
        self._error = None
        stack = self._display_stack = contextlib.ExitStack()
        for name, value in (("layout", self._layout), ("key_bindings", self._bindings), ("erase_when_done", True)):
            stack.callback(setattr, self.app, name, getattr(self.app, name))
            setattr(self.app, name, value)
        self.app.after_render += self._display_started
        stack.callback(self.app.after_render.remove_handler, self._display_started)
        bridge = self._reserved_bridge()
        if bridge is not None:
            # In reserved mode a frame can be skipped, and the after-render event is withheld
            # for those because nothing reached the terminal. Readiness is a different
            # question -- the display is up either way -- so it hangs on the attempt instead.
            bridge.set_render_attempted_handler(self._display_started_without_app)
            stack.callback(bridge.set_render_attempted_handler, None)
        context = contextvars.copy_context()

        def run() -> None:
            try:
                self.app.run(handle_sigint=False, set_exception_handler=False)
            except EOFError:
                pass
            except BaseException as exc:  # noqa: BLE001
                # Propagate startup/render failures to the command thread.
                self._error = exc
            finally:
                self._ready.set()
                self._app_exited()

        self._thread = threading.Thread(target=context.run, args=(run,), name="cmd2-toolbar", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=_STARTUP_TIMEOUT):
            # Bounded so a display that never reports itself started fails here instead of
            # holding the command thread forever. The toolbar is cosmetic; a command waiting
            # indefinitely on one is not a trade anyone would choose.
            raise TimeoutError(f"the bottom toolbar did not start within {_STARTUP_TIMEOUT} seconds")
        if self._error is not None:
            raise self._error
        if self._install_serializers():
            return
        # The worker already combines queued writes. A batching sleep would also
        # delay close(), which runs at each command finalization boundary.
        proxy = _ContextStdoutProxy(raw=True, sleep_between_writes=0)
        with self._lock:
            self._proxy = proxy
            for stream in self._streams:
                stream.proxy = proxy

    def _install_serializers(self) -> bool:
        """Route output straight to the terminal when a reservation is holding the toolbar.

        The stdout proxy exists to put output above a toolbar that scrolls with the screen:
        it erases the toolbar, prints, and draws it again. A reserved toolbar does not scroll,
        so none of that is needed -- and doing it anyway would reintroduce exactly the flicker
        the reservation removes.

        :return: whether serialized writing was installed
        """
        reserved = self.cmd.reserved_toolbar
        if reserved is None or not reserved.is_active:
            return False
        with self._lock:
            self._serialized = True
            for stream in self._streams:
                stream.serializer = SerializedTerminalWriter(stream.original, reserved.lock, reserved.bridge)
        return True

    def _app_exited(self) -> None:
        """Give the terminal back to the streams when the display stops on its own.

        ``_ready`` is set as soon as the first frame renders, so a failure after that is
        never seen by the command thread waiting in ``_resume()``. The display is gone at
        that point and its stdout proxy can no longer reach the terminal, so anything
        written through it would be discarded without a trace.
        """
        if self._pausing:
            # A deliberate pause restores the streams itself, in the right order.
            return

        with self._lock:
            # Leave self._proxy set so that the next _pause() still drains and closes
            # it. With the display gone, its worker writes to the terminal directly.
            started = self._proxy is not None or self._serialized
            for stream in self._streams:
                stream.proxy = None
                stream.serializer = None

        # A proxy exists only once _resume() has handed startup failures to the command
        # thread, so reporting here does not duplicate the exception it raises.
        if started and self._error is not None:
            self.cmd.perror(f"Bottom toolbar stopped after an error: {self._error!r}")

    def _exit(self) -> None:
        """Stop the display unless it has already stopped on its own.

        Application.exit() raises once the result is set, and this runs later than the
        check that scheduled it. Any exception here would reach the loop's default
        handler, which prints a traceback over the terminal.

        Output queued before this does not need draining: Application.run_async() waits
        for cursor position reports and for run_in_terminal() calls still in flight
        before its loop closes.
        """
        if self.app.is_running and not self.app.is_done:
            self.app.exit()

    def _pause(self) -> None:
        self._pausing = True
        try:
            try:
                # Hold off other threads while the proxy drains so their output is never
                # handed to a proxy whose worker has already stopped. Writes that arrive
                # after this go straight to the terminal, still in order.
                with self._lock:
                    try:
                        if self._proxy is not None:
                            self._proxy.flush()
                            self._proxy.close()
                    finally:
                        self._proxy = None
                        self._serialized = False
                        for stream in self._streams:
                            stream.proxy = None
                            # Nothing to drain: a serialized write reaches the terminal
                            # before it returns, so there is no queued work to lose.
                            stream.serializer = None
            finally:
                # The lock is released before joining, since the toolbar thread may be
                # blocked writing through a stream that is waiting on it.
                if self.app.is_running and self.app.loop is not None:
                    self.app.loop.call_soon_threadsafe(self._exit)
                if self._thread is not None:
                    # Bounded, so a render callback blocked inside the display cannot hold the
                    # thread that is tearing it down.
                    self._thread.join(timeout=_SHUTDOWN_TIMEOUT)
                    if self._thread.is_alive():
                        self._abandon_stuck_display()
                    else:
                        self._thread = None
                # Return the borrowed application to the main prompt, including on
                # proxy failures. The upstream toolbar owned a separate application.
                if self._display_stack is not None:
                    self._display_stack.close()
                    self._display_stack = None
                # Application.run() saves its unprocessed queue before the thread
                # exits. Those keys arrived after the ones handled by save_key().
                pending_keys = get_typeahead(self.app.input)
                store_typeahead(self.app.input, self._keys + pending_keys)
                self._keys.clear()
        finally:
            self._pausing = False

    def _abandon_stuck_display(self) -> None:
        """Report that the display did not stop, and refuse to pretend it did.

        A pause that timed out relinquished nothing. The thread is still inside the
        application: still rendering, still reading input. Everything that would normally
        follow a pause assumes the opposite -- the caller hands the terminal to a guest, the
        borrowed layout and key bindings go back to the main prompt, and the display object is
        dropped at the end of the command. Each of those would be acting on an application
        that is still running.

        So nothing further happens here. The application's state is left as the running thread
        expects to find it, and the failure is raised rather than reported and swallowed,
        because only the caller knows what it was about to do with the terminal.

        The refusal is recorded on the application rather than on this object, which the next
        command replaces. The thread outlives it, and one terminal cannot have two input
        readers -- so the application keeps a reference to the display that did not let go,
        and refuses to hand the terminal anywhere until it does.

        :raises _DisplayStillRunningError: always
        """
        self.cmd._command_toolbar_disabled = True
        self.cmd._display_holding_terminal = self
        raise _DisplayStillRunningError(f"the bottom toolbar did not stop within {_SHUTDOWN_TIMEOUT} seconds")

    def stop(self) -> None:
        """Flush output, stop rendering, and restore the terminal and its streams."""
        try:
            for stream in self._streams:
                stream.buffer.finish()
            self._pause()
        finally:
            if self._stack is not None:
                self._stack.close()
                self._stack = None

    @property
    def thread_is_alive(self) -> bool:
        """Whether the display's thread is still running."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_active(self) -> bool:
        """Whether the display currently owns the terminal."""
        return (self._proxy is not None or self._serialized) and self.app.is_running

    def _call_in_ui(self, func: Callable[[], _R]) -> _R:
        """Change UI state on its event loop, propagating failures to the command."""
        result: Future[_R] = Future()

        def call() -> None:
            try:
                value = func()
            except BaseException as exc:  # noqa: BLE001
                result.set_exception(exc)
            else:
                result.set_result(value)

        if self.app.loop is None:
            raise RuntimeError("Toolbar is not running")
        self.app.loop.call_soon_threadsafe(call)
        while True:
            try:
                value = result.result(timeout=0.1)
            except FutureTimeoutError:
                if result.done():
                    # The callback finished while this poll was expiring, or raised a
                    # TimeoutError of its own -- indistinguishable here, because
                    # concurrent.futures.TimeoutError is TimeoutError on Python 3.11+.
                    # Ask the future for its outcome rather than re-raising this poll's
                    # timeout, which would report a failure for a call that succeeded.
                    return result.result()
                self._check_running()
            else:
                return value

    def _check_running(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            if self._error is not None:
                raise self._error
            raise EOFError

    def page(self, text: str, *, chop: bool) -> None:
        """Show a pager above the same toolbar without starting another input reader."""
        size = self.app.output.get_size()
        # Measuring the toolbar can invoke its callback; keep that work on the
        # UI thread along with rendering and layout changes.
        toolbar_height = self._call_in_ui(lambda: self.toolbar.preferred_height(size.columns, size.rows).preferred)
        if output_fits(text, size.columns, max(0, size.rows - toolbar_height), chop=chop):
            self.cmd.stdout.write(text)
            self.cmd.stdout.flush()
            return

        pager = Pager(text, chop=chop)
        pager.bindings.add(
            "c-z",
            filter=Condition(lambda: suspend_to_background_supported() and to_filter(self.cmd.main_session.enable_suspend)()),
        )(self._suspend_binding)
        layout = Layout(HSplit([pager.container, self.toolbar]), focused_element=pager.text)
        previous = (self.app.layout, self.app.key_bindings, self.app.editing_mode, self.app.full_screen)
        entered = False

        def enter() -> None:
            nonlocal entered
            entered = True
            self.app.renderer.erase()
            self.app.layout = layout
            self.app.key_bindings = pager.bindings
            self.app.editing_mode = EditingMode.EMACS
            self.app.full_screen = self.app.renderer.full_screen = True
            self.app.invalidate()

        def leave() -> None:
            nonlocal entered
            if not entered:
                return
            entered = False
            self.app.renderer.erase()
            self.app.layout, self.app.key_bindings, self.app.editing_mode, self.app.full_screen = previous
            self.app.renderer.full_screen = self.app.full_screen
            self.app.renderer.request_absolute_cursor_position()
            self.app.invalidate()

        def close() -> None:
            # Switch bindings before the next key is processed, preserving
            # typeahead sent in the same terminal read as the pager's quit key.
            leave()
            pager.closed.set()

        pager.on_close = close

        try:
            self._call_in_ui(enter)
            while not pager.closed.wait(0.1):
                self._check_running()
        finally:
            if self._thread is not None and self._thread.is_alive():
                self._call_in_ui(leave)
            else:
                # The application's shutdown already reset the renderer.
                self.app.layout, self.app.key_bindings, self.app.editing_mode, self.app.full_screen = previous
                self.app.renderer.full_screen = self.app.full_screen

    @contextlib.contextmanager
    def suspend(self) -> Iterator[None]:
        """Temporarily restore ordinary terminal access, including nested suspensions.

        Whether output is proxied or serialized, what has to stop is the display: its renderer
        draws and its input reader reads, and a guest given the terminal alongside either of
        them is sharing it rather than owning it.
        """
        if self._proxy is None and not self._serialized:
            yield
            return
        with self.cmd.sigint_protection:
            self._pause()
        try:
            yield
        finally:
            with self.cmd.sigint_protection:
                self._resume()
