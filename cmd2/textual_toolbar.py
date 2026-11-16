"""PROTOTYPE: a bottom toolbar drawn by Textual instead of prompt-toolkit.

A third way to keep the bottom toolbar on the screen while a command runs. The other two have
prompt-toolkit draw it, in a terminal which cmd2 is also writing command output to. Here cmd2
does not draw the toolbar at all:

- A small Textual application, the *host*, owns the real terminal. It shows a terminal emulator
  (the ``Terminal`` widget of textual-tty) with a one-widget toolbar docked below it.
- The cmd2 application runs as a child process inside that emulator, exactly as it would in
  any terminal. It is the same program run again, with an environment variable to tell it so.
- The child sends the content of ``Cmd.get_bottom_toolbar()`` to the host over a Unix socket,
  from a thread, so it keeps coming while a command has the main thread.

Since the emulator and the toolbar are different widgets, command output cannot reach the
toolbar's rows, and Textual redraws only what changed.

Use :func:`run` in place of ``sys.exit(MyApp().cmdloop())``::

    if __name__ == "__main__":
        sys.exit(cmd2.textual_toolbar.run(MyApp))

Neither textual nor textual-tty is a dependency of cmd2. Without them, on Windows, or when
stdin or stdout is not a terminal, :func:`run` runs the application as it always did.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Self

from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import AnyFormattedText, to_formatted_text
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.renderer import print_formatted_text
from prompt_toolkit.styles import DynamicStyle, default_ui_style, merge_styles

from .plugin import CommandFinalizationData, PostparsingData
from .theme import get_pt_theme

if TYPE_CHECKING:  # pragma: no cover
    from .cmd2 import Cmd

#: Set in the environment of a cmd2 application which a host is running, to the path of the
#: Unix socket the host listens on for its toolbar.
HOST_SOCKET_ENV = "CMD2_TEXTUAL_TOOLBAR"

#: Control sequences other than "select graphic rendition", which is how a style is written.
_NOT_A_STYLE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-ln-~]")

#: How often the toolbar's content is looked at when the application has no refresh interval.
DEFAULT_INTERVAL = 0.5


def is_hosted() -> bool:
    """Return whether this process is a cmd2 application running inside a Textual host."""
    return bool(os.environ.get(HOST_SOCKET_ENV))


def can_host() -> bool:
    """Return whether a Textual host can be started here for this program."""
    return (
        sys.platform != "win32"
        and sys.stdin.isatty()
        and sys.stdout.isatty()
        and importlib.util.find_spec("textual") is not None
        and importlib.util.find_spec("textual_tty") is not None
    )


def render_ansi(content: AnyFormattedText) -> str:
    """Render a toolbar's content as text with ANSI style sequences, for the host to draw.

    prompt-toolkit does the rendering, so anything ``get_bottom_toolbar()`` may return is
    understood, and style classes mean what cmd2's theme says they mean.

    :param content: what ``get_bottom_toolbar()`` returned
    :return: the text, with a newline between rows
    """
    stream = io.StringIO()
    output = Vt100_Output(
        stream,
        lambda: Size(rows=1, columns=10_000),
        term="xterm-256color",
        default_color_depth=ColorDepth.TRUE_COLOR,
        enable_bell=False,
        enable_cpr=False,
    )
    # The theme over prompt-toolkit's default style, as an application has them: <b> is only
    # bold because the default style says so.
    style = merge_styles([default_ui_style(), DynamicStyle(get_pt_theme)])
    print_formatted_text(output, to_formatted_text(content), style, color_depth=ColorDepth.TRUE_COLOR)
    # Only the styles are the host's business, not what else the renderer sets up around them.
    return _NOT_A_STYLE.sub("", stream.getvalue()).replace("\r\n", "\n")


class ToolbarReporter:
    """Sends a toolbar's content to the host whenever it changes.

    Runs in the cmd2 application, on a thread of its own, so the toolbar goes on being
    refreshed while a command is running.
    """

    def __init__(
        self, get_toolbar: Callable[[], AnyFormattedText], interval: float = DEFAULT_INTERVAL, path: str | None = None
    ) -> None:
        """Prepare to report a toolbar.

        :param get_toolbar: returns the toolbar's content, as ``Cmd.get_bottom_toolbar()`` does
        :param interval: seconds between looks at the content
        :param path: the host's socket, which is otherwise found in the environment
        """
        self._get_toolbar = get_toolbar
        self._path = path
        self._interval = interval if interval > 0 else DEFAULT_INTERVAL
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._wake = threading.Event()
        self._stopping = False
        self._last: str | None = None

    def start(self) -> None:
        """Connect to the host and start reporting."""
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.connect(self._path or os.environ[HOST_SOCKET_ENV])
        self._socket = connection
        self._report()
        self._thread = threading.Thread(target=self._run, name="cmd2-textual-toolbar", daemon=True)
        self._thread.start()

    def poke(self) -> None:
        """Look at the content now, without waiting for the interval: something has changed."""
        self._wake.set()

    def stop(self) -> None:
        """Stop reporting and close the connection."""
        self._stopping = True
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self) -> Self:
        """Start reporting."""
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        """Stop reporting."""
        self.stop()

    def _run(self) -> None:
        while not self._stopping:
            self._wake.wait(self._interval)
            self._wake.clear()
            if self._stopping or not self._report():
                return

    def _report(self) -> bool:
        """Send the content if it has changed.

        :return: whether the host is still there
        """
        try:
            rendered = render_ansi(self._get_toolbar())
        except Exception:  # noqa: BLE001 - a toolbar callback must not end the application
            # The last good content stays on the screen.
            return True
        if rendered == self._last or self._socket is None:
            return True
        try:
            self._socket.sendall(json.dumps({"toolbar": rendered}).encode() + b"\n")
        except OSError:
            return False
        self._last = rendered
        return True


def run(app_factory: Callable[[], "Cmd"]) -> int:
    """Run a cmd2 application with its bottom toolbar drawn by a Textual host.

    Called first by the program the user started. That one starts the host, which runs the same
    program again inside itself, and there this function creates the application and runs its
    command loop. So the application is only ever created in the process which uses it.

    :param app_factory: creates the cmd2 application, usually its class
    :return: the application's exit code
    """
    if not is_hosted():
        if not can_host():
            return app_factory().cmdloop()
        return run_host([sys.executable, *sys.orig_argv[1:]])

    app = app_factory()
    # The application has been built knowing it is hosted. Programs it runs are not: one of
    # them could be another cmd2 application, and would take this one's toolbar.
    path = os.environ.pop(HOST_SOCKET_ENV)
    reporter = ToolbarReporter(app.get_bottom_toolbar, getattr(app.main_session, "refresh_interval", 0) or 0, path)

    # A command starting or ending is when a toolbar most often changes. Don't wait for it.
    def command_started(data: PostparsingData) -> PostparsingData:
        reporter.poke()
        return data

    def command_finished(data: CommandFinalizationData) -> CommandFinalizationData:
        reporter.poke()
        return data

    app.register_postparsing_hook(command_started)
    app.register_cmdfinalization_hook(command_finished)
    with reporter:
        return app.cmdloop()


def run_host(command: list[str]) -> int:
    """Run a program in a terminal emulator with a toolbar below it, until the program exits.

    :param command: the program and its arguments
    :return: the program's exit code
    """
    directory = tempfile.mkdtemp(prefix="cmd2-toolbar-")
    path = os.path.join(directory, "toolbar.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        # Listening before the program is started, so its connection is never refused.
        listener.bind(path)
        listener.listen(1)
        # The emulator copies the environment when it is first imported, so this comes first.
        os.environ[HOST_SOCKET_ENV] = path
        try:
            app = build_host_app(command, listener)
            app.run()
            return int(app.program_exit_code)
        finally:
            del os.environ[HOST_SOCKET_ENV]
    finally:
        listener.close()
        shutil.rmtree(directory, ignore_errors=True)


def build_host_app(command: list[str], listener: socket.socket) -> Any:
    """Build the Textual application which hosts a program. Textual is only imported here.

    :param command: the program and its arguments
    :param listener: a listening Unix socket, whose path the program has in its environment
    :return: the application, whose ``program_exit_code`` is the program's once it has run
    """
    import asyncio

    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.message import Message
    from textual.widgets import Static
    from textual_tty import Terminal  # type: ignore[import-untyped]

    class ToolbarChanged(Message):
        """The program has new content for its toolbar."""

        def __init__(self, rendered: str) -> None:
            self.rendered = rendered
            super().__init__()

    class ToolbarHost(App[None]):
        """A terminal emulator running the program, and its toolbar."""

        CSS = """
        #program {
            height: 1fr;
        }
        #toolbar {
            dock: bottom;
            height: auto;
            min-height: 1;
            background: $foreground;
            color: $background;
        }
        """
        ENABLE_COMMAND_PALETTE = False

        def __init__(self) -> None:
            super().__init__()
            self.program_exit_code = 0
            self._server: asyncio.Server | None = None

        def compose(self) -> ComposeResult:
            yield Terminal(command=command, id="program")
            yield Static("", id="toolbar")

        async def on_mount(self) -> None:
            self._server = await asyncio.start_unix_server(self._toolbar_connection, sock=listener)
            self.query_one(Terminal).focus()

        async def on_unmount(self) -> None:
            if self._server is not None:
                self._server.close()

        async def _toolbar_connection(self, reader: asyncio.StreamReader, _writer: asyncio.StreamWriter) -> None:
            """Read toolbar content from the program, one JSON document to a line."""
            while line := await reader.readline():
                with contextlib.suppress(ValueError, TypeError):
                    document = json.loads(line)
                    if isinstance(document, dict) and isinstance(document.get("toolbar"), str):
                        self.post_message(ToolbarChanged(document["toolbar"]))

        def on_toolbar_changed(self, message: ToolbarChanged) -> None:
            self.query_one("#toolbar", Static).update(Text.from_ansi(message.rendered))

        def on_terminal_process_exited(self, event: Any) -> None:
            code = event.exit_code
            # A process killed by a signal has the negated signal number. Shells say 128 + signal.
            self.program_exit_code = 128 - code if code < 0 else code
            self.exit()

    return ToolbarHost()
