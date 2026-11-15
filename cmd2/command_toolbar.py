"""Internal support for displaying a toolbar during synchronous commands."""

import asyncio
import codecs
import contextlib
import contextvars
import functools
import os
import re
import signal
import sys
import threading
import time
from collections.abc import Callable, Generator
from typing import TYPE_CHECKING, Any, TextIO, TypeVar, cast

from prompt_toolkit.application import Application, create_app_session, run_in_terminal
from prompt_toolkit.filters import Condition, to_filter
from prompt_toolkit.input.typeahead import get_typeahead, store_typeahead
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_processor import KeyPress, KeyPressEvent
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.patch_stdout import StdoutProxy
from prompt_toolkit.utils import get_cwidth, suspend_to_background_supported

if TYPE_CHECKING:
    from .cmd2 import Cmd

# Control sequences, operating system commands, and two-character escapes: text which takes
# no room on the screen.
_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")

_F = TypeVar("_F", bound=Callable[..., Any])


def suspend_process_group(suspend_group: bool = True) -> None:
    """Stop this process, or its whole process group, with SIGTSTP from any thread.

    A process-directed stop signal can be taken by a thread other than the sender. Sent
    from the display thread, it lands on the main thread, and the display thread carries
    on for a few milliseconds: it puts the terminal back into raw mode and redraws before
    the job has stopped. When the shell resumes the job it restores the modes it saved
    beforehand, and nothing is left to undo that -- the terminal stays cooked, keys are
    held until Enter, and every cursor-position query is echoed as ``^[[row;colR``.

    So after sending the signal this thread waits for the stop to take it too. A stop
    shows as time passing while asleep; a signal that was ignored, or discarded for an
    orphaned process group, shows as nothing, and the wait ends on its own.

    :param suspend_group: stop the whole process group, as a shell's Ctrl-Z would, rather
        than only this process
    """
    if not hasattr(signal, "SIGTSTP"):  # pragma: no cover - POSIX only
        return
    os.kill(0 if suspend_group else os.getpid(), signal.SIGTSTP)
    deadline = time.monotonic() + 0.25
    while (before := time.monotonic()) < deadline:
        time.sleep(0.01)
        if time.monotonic() - before > 0.1:
            return


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
    """Print above the toolbar from its isolated application session, keeping unfinished lines.

    prompt-toolkit draws the toolbar starting at the cursor, and erases it from the first
    column of that row before printing anything more. Output which stopped in the middle of
    a line, such as ``Working...`` or a progress line ending in a carriage return, would be
    erased with it. So a line left unfinished is ended on the screen, which gives the toolbar
    a row of its own, and it is continued from where it stopped when more output arrives.
    """

    def __init__(self, toolbar_rows: Callable[[], int] = lambda: 1) -> None:
        """Start printing above a toolbar.

        :param toolbar_rows: returns how many rows the toolbar takes below the output
        """
        # The line which output last left unfinished, exactly as written. Set before the
        # base class starts the thread which reads it.
        self._unfinished = ""
        self._toolbar_rows = toolbar_rows
        # The worker already combines queued writes. A batching sleep would also delay
        # close(), which runs at each command finalization boundary.
        super().__init__(raw=True, sleep_between_writes=0)

    def _start_write_thread(self) -> threading.Thread:
        context = contextvars.copy_context()
        thread = threading.Thread(target=context.run, args=(self._write_thread,), daemon=True)
        thread.start()
        return thread

    def _write_and_flush(self, loop: asyncio.AbstractEventLoop | None, text: str) -> None:
        """Write text above the toolbar as the base class does, continuing an unfinished line."""

        def write_and_flush() -> None:
            output = self._output
            # See the base class: Windows resets autowrap at each flush.
            output.enable_autowrap()
            if self._unfinished:
                # The cursor is at the start of the row below the unfinished line. Go back
                # to the row its last carriage return left it on, and write the rest of
                # it again to put the cursor, and any style it set, where they were.
                output.cursor_up(self._rows(self._unfinished))
                output.write_raw(self._unfinished)
            output.write_raw(text)
            line = self._last_line(self._unfinished + text)
            if line:
                output.write_raw("\r\n")
            # A line whose start has scrolled off the screen can't be found again, so it
            # stays ended where it is. Its first row scrolls off once the screen has no
            # room for the whole line and the toolbar below it. A row is needed below the
            # line even with no toolbar, for the cursor which ended it.
            room = output.get_size().rows - max(1, self._toolbar_rows())
            self._unfinished = line if self._rows(line) <= room else ""
            output.flush()

        if loop is None:
            write_and_flush()
        else:
            loop.call_soon_threadsafe(lambda: run_in_terminal(write_and_flush, in_executor=False))

    @staticmethod
    def _last_line(text: str) -> str:
        """Return what must be written again to continue the line which text leaves unfinished.

        :param text: everything written since the last finished line
        :return: the unfinished line from its last carriage return, or "" if the last line is
            finished
        """
        line = text.rpartition("\n")[2]
        if not line.strip("\r"):
            # Nothing has been written on this row, wherever the cursor returned to.
            return ""
        # A carriage return went back to the start of the row the cursor is on, so nothing
        # before it is needed to find that place again. Dropping it also keeps a progress
        # line which is redrawn thousands of times from growing without bound.
        return line[max(0, line.rfind("\r")) :]

    def _rows(self, line: str) -> int:
        """Return how many rows below its start the cursor was left after line was ended."""
        width = self._width(line)
        columns = self._wrap_columns()
        if self._wraps_at_once():
            # A line which has just filled a row has put the cursor on the next one.
            return width // columns + 1
        return max(1, -(-width // columns))

    def _wraps_at_once(self) -> bool:
        """Return whether the terminal moves to the next row as soon as a row is full.

        A terminal which understands escape sequences waits for the next character. A legacy
        Windows console does not wait. It gets prompt-toolkit's Win32Output which, unlike its
        other Windows outputs, has no vt100 output to write escape sequences with.
        """
        output = self._output
        return hasattr(output, "get_win32_screen_buffer_info") and not hasattr(output, "vt100_output")

    def _wrap_columns(self) -> int:
        """Return how many columns the terminal fits on a row before it wraps a line.

        prompt-toolkit's Windows outputs report one column fewer than the console has, which
        keeps what prompt-toolkit draws out of the last column. Text written raw is wrapped by
        the console itself, at the width of its screen buffer.
        """
        screen_buffer_info = getattr(self._output, "get_win32_screen_buffer_info", None)
        if screen_buffer_info is not None:
            return max(1, int(screen_buffer_info().dwSize.X))
        return max(1, self._output.get_size().columns)

    @staticmethod
    def _width(line: str) -> int:
        return get_cwidth(_ESCAPE_RE.sub("", line))


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
        # Set once the display has stopped after an error. It is reported once and not
        # restarted, so a callback which keeps failing cannot repeat that at every pause.
        self._failed = False

        session = cmd.main_session
        self.app = session.app
        # Ctrl-Z during a command is handled on the display's thread, where upstream's
        # version would not hold the thread until the job has stopped.
        if "suspend_to_background" not in vars(self.app):
            cast("Any", self.app).suspend_to_background = self._suspend_to_background
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
        self._toolbar_window = self.toolbar.content
        # The rows the toolbar took when it was last drawn, to begin with by the main prompt.
        # Each run of the application forgets what it drew, and prompt-toolkit leaves the
        # toolbar out until the terminal has reported where its cursor is, which can be after
        # a command's first output. The toolbar is about to take these rows again.
        self._toolbar_height = 0
        self._note_toolbar_height()
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

    @staticmethod
    def _suspend_to_background(suspend_group: bool = True) -> None:
        """Suspend like upstream's ``Application.suspend_to_background()``, from any thread."""
        run_in_terminal(functools.partial(suspend_process_group, suspend_group))

    def _after_render(self, app: Application[str]) -> None:  # noqa: ARG002
        self._note_toolbar_height()
        self._ready.set()

    def _note_toolbar_height(self) -> None:
        """Remember how many rows the toolbar took, if the last frame drew it."""
        info = self._toolbar_window.render_info
        if info is not None:
            self._toolbar_height = info.window_height

    def _toolbar_rows(self) -> int:
        """Return how many rows the toolbar took when it was last drawn."""
        return self._toolbar_height

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
        if self._failed:
            return
        self._ready.clear()
        self._error = None
        stack = self._display_stack = contextlib.ExitStack()
        # Replace key_bindings only together with a layout whose focused window prompt-toolkit
        # has not seen with other bindings. It caches the bindings it merges for each focused
        # window, application bindings included, and does not notice this attribute being
        # reassigned, so reusing a window with different bindings would keep the old ones.
        # This layout and the main prompt's have windows of their own.
        for name, value in (("layout", self._layout), ("key_bindings", self._bindings), ("erase_when_done", True)):
            stack.callback(setattr, self.app, name, getattr(self.app, name))
            setattr(self.app, name, value)
        self.app.after_render += self._after_render
        stack.callback(self.app.after_render.remove_handler, self._after_render)
        context = contextvars.copy_context()

        def run() -> None:
            try:
                self.app.run(pre_run=self._handle_loop_errors, handle_sigint=False, set_exception_handler=False)
            except EOFError:
                pass
            except BaseException as exc:  # noqa: BLE001
                # Propagate startup/render failures to the command thread. Stopping after an
                # error in the loop draws a last frame, and a failure there is only a
                # consequence of the error already recorded.
                if self._error is None:
                    self._error = exc
            finally:
                self._ready.set()
                self._app_exited()

        self._thread = threading.Thread(target=context.run, args=(run,), name="cmd2-toolbar", daemon=True)
        self._thread.start()
        self._ready.wait()
        if self._error is not None:
            raise self._error
        proxy = _ContextStdoutProxy(self._toolbar_rows)
        with self._lock:
            self._proxy = proxy
            for stream in self._streams:
                stream.proxy = proxy

    def _handle_loop_errors(self) -> None:
        """Stop the display on the first unhandled error in its event loop.

        prompt-toolkit's own handler prints the traceback and waits for Enter, which would
        hold up a command that is still running. With no handler at all, asyncio logs each
        error to stderr. That write goes through the stdout proxy, whose redraw of the
        toolbar calls a failing ``get_bottom_toolbar()`` again, so a single faulty callback
        buries the command's output in tracebacks for as long as the command runs.
        """
        asyncio.get_running_loop().set_exception_handler(self._loop_error)

    def _loop_error(self, loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:  # noqa: ARG002
        """Record the first error for the command thread and end the display.

        ``_resume()`` raises it if the display has not finished starting. After that,
        ``_app_exited()`` reports it once.
        """
        if self._error is None:
            self._error = context.get("exception") or RuntimeError(context.get("message", "unknown error"))
        self._exit()

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
            self._report_failure(self._error)

    def _report_failure(self, error: BaseException) -> None:
        """Say once that the command carries on without its toolbar."""
        if not self._failed:
            self._failed = True
            self.cmd.perror(f"Bottom toolbar stopped after an error: {error!r}")

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
                # Write any window title whose callback the display's loop didn't run. The display
                # has stopped, so this can't interleave with its rendering.
                self.cmd._flush_pending_window_title_quietly()
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

    @contextlib.contextmanager
    def suspend(self) -> Generator[None]:
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
                try:
                    self._resume()
                except Exception as exc:  # noqa: BLE001
                    # The toolbar is cosmetic. A display that cannot come back must not fail
                    # the command which paused it, nor escape cmdloop() from command
                    # finalization. The command carries on without one, and stop() still
                    # returns the borrowed application to the main prompt.
                    self._report_failure(exc)
