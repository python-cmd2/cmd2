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
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.input.typeahead import get_typeahead, store_typeahead
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.key_processor import KeyPress, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.patch_stdout import StdoutProxy
from prompt_toolkit.utils import suspend_to_background_supported

from .pager import Pager, output_fits

if TYPE_CHECKING:
    from prompt_toolkit.buffer import Buffer

    from .cmd2 import Cmd

    #: The prompt text, or a callable returning it for a dynamic prompt.
    PromptMessage = Callable[[], ANSI | str] | ANSI | str

_F = TypeVar("_F", bound=Callable[..., Any])
_R = TypeVar("_R")


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

        # Prompt mode reuses the PromptSession's own layout, so completion menus,
        # auto-suggestions, and the rprompt all keep working. Only the accept path
        # changes: it hands the line to the command thread instead of ending the run.
        self._prompt_layout = session.layout

        prompt_bindings = KeyBindings()

        @prompt_bindings.add("c-c")
        def prompt_interrupt(event: KeyPressEvent) -> None:  # noqa: ARG001
            # PromptSession aborts by calling app.exit(), which would end the run that
            # draws the toolbar. Fail the pending read instead and keep rendering.
            self._fail_line(KeyboardInterrupt())

        @prompt_bindings.add("c-d", filter=Condition(lambda: not self.app.current_buffer.text))
        def prompt_eof(event: KeyPressEvent) -> None:  # noqa: ARG001
            self._fail_line(EOFError())

        # session.app.key_bindings is captured before _resume() swaps in the command
        # display's set, so it is the PromptSession's own: completion, history, and
        # cmd2's bindings. Merging the overrides last lets them win, because
        # KeyProcessor calls matches[-1].
        self._prompt_bindings = merge_key_bindings([session.app.key_bindings, prompt_bindings])
        self._line: Future[str] | None = None
        # Only swapped in for the duration of read_line(). session.prompt() still runs
        # nested prompts and the no-toolbar fallback, and those rely on the stock
        # handler's app.exit() to return at all.
        self._session_accept = session.default_buffer.accept_handler

    def _after_render(self, app: Application[str]) -> None:  # noqa: ARG002
        self._ready.set()

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
        stack = self._display_stack = contextlib.ExitStack()
        for name, value in (("layout", self._layout), ("key_bindings", self._bindings), ("erase_when_done", True)):
            stack.callback(setattr, self.app, name, getattr(self.app, name))
            setattr(self.app, name, value)
        self.app.after_render += self._after_render
        stack.callback(self.app.after_render.remove_handler, self._after_render)
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
    def is_active(self) -> bool:
        """Whether the display currently owns the terminal."""
        return self._proxy is not None and self.app.is_running

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
                    raise
                self._check_running()
            else:
                return value

    def _check_running(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            if self._error is not None:
                raise self._error
            raise EOFError

    def _accept_line(self, buff: "Buffer") -> bool:
        """Hand an accepted line to the waiting command thread without ending the run."""
        if self._line is not None and not self._line.done():
            self._line.set_result(buff.document.text)
        # Discard the text so the live prompt region stops showing the accepted line.
        # _echo_accepted() is what commits it, and leaving it here too would draw it
        # twice. validate_and_handle() still records history before resetting.
        return False

    def _fail_line(self, error: BaseException) -> None:
        """Abort the pending read_line() with Ctrl-C's or Ctrl-D's exception."""
        if self._line is not None and not self._line.done():
            self._line.set_exception(error)

    def read_line(
        self,
        message: "PromptMessage",
        *,
        pre_run: Callable[[], None] | None = None,
    ) -> str:
        """Read one line at the prompt while the toolbar's application keeps running.

        :param message: the prompt text, or a callable returning it for a dynamic prompt
        :param pre_run: optional callback run on the UI thread once the prompt is shown
        :return: the accepted line
        :raises KeyboardInterrupt: if the user pressed Ctrl-C
        :raises EOFError: if the user pressed Ctrl-D on an empty line
        """
        line: Future[str] = Future()
        self._line = line
        session = self.cmd.main_session

        def enter() -> None:
            session.message = message
            session.default_buffer.reset()
            session.default_buffer.accept_handler = self._accept_line
            self.app.layout = self._prompt_layout
            self.app.layout.focus(session.default_buffer)
            self.app.key_bindings = self._prompt_bindings
            if pre_run is not None:
                pre_run()
            self.app.invalidate()

        try:
            self._call_in_ui(enter)
            while True:
                try:
                    text = line.result(timeout=0.1)
                except FutureTimeoutError:
                    if line.done():
                        raise
                    self._check_running()
                else:
                    self._echo_accepted(message, text)
                    return text
        finally:
            self._line = None
            session.default_buffer.accept_handler = self._session_accept

    @staticmethod
    def _resolve_message(message: "PromptMessage") -> str:
        """Render the prompt to text for the scrollback echo."""
        resolved = message() if callable(message) else message
        return resolved.value if isinstance(resolved, ANSI) else resolved

    def _echo_accepted(self, message: "PromptMessage", text: str) -> None:
        """Commit the accepted line above the toolbar.

        prompt-toolkit normally leaves the prompt line in the scrollback when its run
        ends. Prompt mode never ends a run, so write the line through the same stdout
        proxy that keeps command output above the toolbar.
        """
        self.cmd.stdout.write(f"{self._resolve_message(message)}{text}\n")
        self.cmd.stdout.flush()

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
