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
from typing import TYPE_CHECKING, Any, TextIO, TypeVar, cast

from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.filters import Condition, is_done, renderer_height_is_known, to_filter
from prompt_toolkit.input.typeahead import get_typeahead, store_typeahead
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPress, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.patch_stdout import StdoutProxy
from prompt_toolkit.utils import suspend_to_background_supported

if TYPE_CHECKING:
    from .cmd2 import Cmd

_F = TypeVar("_F", bound=Callable[..., Any])


def suspend_toolbar(func: _F) -> _F:
    """Give a method exclusive access to the terminal."""

    @functools.wraps(func)
    def wrapped(self: "Cmd", *args: Any, **kwargs: Any) -> Any:
        with self.suspend_bottom_toolbar():
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


class _ContextStdoutProxy(StdoutProxy):
    """Keep stdout's flush worker in the toolbar's isolated application session."""

    def _start_write_thread(self) -> threading.Thread:
        context = contextvars.copy_context()
        thread = threading.Thread(target=context.run, args=(self._write_thread,), daemon=True)
        thread.start()
        return thread


class ToolbarStream:
    """Keep a stable stream identity across suspensions and cmd2 redirections."""

    def __init__(self, original: TextIO, lock: "threading.RLock") -> None:
        """Wrap a terminal stream while preserving its ordinary file attributes."""
        self.original = original
        self.proxy: StdoutProxy | None = None
        # Shared with the toolbar so a write from another thread cannot land on a proxy
        # that is being closed. Such a write is accepted by the dead proxy and discarded.
        self._lock = lock
        self.buffer = _ToolbarBuffer(self)

    def write(self, data: str) -> int:
        """Write above the toolbar, or directly while the toolbar is suspended."""
        with self._lock:
            return (self.proxy or self.original).write(data)

    def flush(self) -> None:
        """Flush the currently active output stream."""
        with self._lock:
            (self.proxy or self.original).flush()

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
    """Run a prompt-toolkit display in a thread while a command runs on the main thread.

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
        self._lock = threading.RLock()
        self._pausing = False

        session = cmd.main_session
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

        self.app: Application[None] = Application(
            layout=Layout(
                HSplit(
                    [
                        Window(height=0),
                        Window(),
                        ConditionalContainer(
                            Window(
                                FormattedTextControl(lambda: session.bottom_toolbar, style="class:bottom-toolbar.text"),
                                style="class:bottom-toolbar",
                                height=1,
                                always_hide_cursor=True,
                            ),
                            filter=~is_done & renderer_height_is_known,
                        ),
                    ]
                )
            ),
            input=session.input,
            output=session.output,
            style=session.style,
            color_depth=session.color_depth,
            refresh_interval=session.refresh_interval,
            key_bindings=bindings,
            erase_when_done=True,
            after_render=lambda _: self._ready.set(),
        )

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
            self.stop()
            raise

    @staticmethod
    def _restore_stream(obj: Any, name: str, stream: ToolbarStream) -> None:
        if getattr(obj, name) is stream:
            setattr(obj, name, stream.original)

    def _resume(self) -> None:
        self._ready.clear()
        self._error = None
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
        self._ready.wait()
        if self._error is not None:
            raise self._error
        # The worker already combines queued writes. A batching sleep would also
        # delay close(), which runs at each command finalization boundary.
        proxy = _ContextStdoutProxy(raw=True, sleep_between_writes=0)
        with self._lock:
            self._proxy = proxy
            for stream in self._streams:
                stream.proxy = proxy

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
            started = self._proxy is not None
            for stream in self._streams:
                stream.proxy = None

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
        if self.app.is_running:
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
                        for stream in self._streams:
                            stream.proxy = None
            finally:
                # The lock is released before joining, since the toolbar thread may be
                # blocked writing through a stream that is waiting on it.
                if self.app.is_running and self.app.loop is not None:
                    self.app.loop.call_soon_threadsafe(self._exit)
                if self._thread is not None:
                    self._thread.join()
                    self._thread = None
                # Application.run() saves its unprocessed queue before the thread
                # exits. Those keys arrived after the ones handled by save_key().
                pending_keys = get_typeahead(self.app.input)
                store_typeahead(self.app.input, self._keys + pending_keys)
                self._keys.clear()
        finally:
            self._pausing = False

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

    @contextlib.contextmanager
    def suspend(self) -> Iterator[None]:
        """Temporarily restore ordinary terminal access, including nested suspensions."""
        if self._proxy is None:
            yield
            return
        with self.cmd.sigint_protection:
            self._pause()
        try:
            yield
        finally:
            with self.cmd.sigint_protection:
                self._resume()
