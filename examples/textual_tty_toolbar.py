#!/usr/bin/env python3
"""Keep a bottom toolbar on the screen while commands run, by letting Textual draw it using textual-tty.

cmd2's bottom toolbar is drawn by prompt-toolkit as part of the prompt, so it is only there while the prompt is.
This example shows a way to have one which stays, and keeps refreshing, while a command runs: the cmd2
application doesn't draw the toolbar at all. A small Textual application owns the terminal instead. It shows the
cmd2 application in a terminal pane which fills the screen except for the bottom, where it draws the toolbar.

How it works:
  - [textual-tty](https://github.com/ttygroup/textual-tty) provides the ``Terminal`` widget, a terminal
    emulator (built on bittty) which runs a child process attached to a pseudo-terminal.
  - The child process is this script run with ``--cmd2-only --toolbar-socket PATH``. It is a normal cmd2
    application which uses prompt-toolkit, except that it gives prompt-toolkit no toolbar to draw.
  - A thread in the cmd2 application calls ``get_bottom_toolbar()`` every half second, and at once when a
    command starts or ends, and sends what it returns to the Textual application over a Unix socket. Since it
    is a thread, it keeps doing so while a command has the main thread.
  - The Textual application puts what it receives in a widget docked below the terminal pane. Command output
    can't overwrite the toolbar, or make it flicker, because it goes to a different widget.

The sibling example ``textual_tty_embed.py`` sends its status through the terminal's window title instead of a
socket, which is simpler. That works there because the status is only sent from hooks, between a command's
output. A toolbar which refreshes during a command is sent from another thread, and a window title written into
the terminal's stream from another thread could land in the middle of the command's output.

Things this approach gives up, which is why cmd2 doesn't do it for you:
  - Scrollback. The terminal pane keeps none, so output which scrolls off its top is gone, and Textual uses
    the terminal's alternate screen, so none of the session is in your terminal's own scrollback either.
    Pipe long output to a pager.
  - Windows. On Windows textual-tty can only start a program by name and can't pass it arguments.
  - Ctrl-Z does nothing, because inside the pane there is no shell to return to.
  - Textual takes the mouse, so selecting text the way your terminal does it needs your terminal's modifier key.

Neither textual nor textual-tty are dependencies of cmd2. In a cmd2 checkout, textual-tty is part of the
development environment on POSIX systems, so run this example with:

    uv run examples/textual_tty_toolbar.py

Otherwise, install textual-tty into your own environment with ``pip install textual-tty`` and then run
``python examples/textual_tty_toolbar.py``.

Things to try: ``slow``, ``burst 2000 1``, ``page``, ``ask``, resizing the window while a command runs, and
Ctrl-C during ``slow``. To compare with what cmd2 does on its own, run just the cmd2 application, on any platform:

    python examples/textual_tty_toolbar.py --cmd2-only

Use the ``quit`` command in the cmd2 application, or press Ctrl-Q, to exit.
"""

import argparse
import contextlib
import io
import json
import re
import shutil
import socket
import sys
import tempfile
import threading
import time
from collections.abc import Callable

from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import AnyFormattedText, to_formatted_text
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.renderer import print_formatted_text
from prompt_toolkit.styles import DynamicStyle, default_ui_style, merge_styles

import cmd2
from cmd2.theme import get_pt_theme

# Control sequences other than "select graphic rendition", which is how a style is written. A control sequence ends with
# a final byte from "@" to "~" which says what it does, and the last character class is every one of those except the "m"
# of "select graphic rendition".
NOT_A_STYLE = re.compile(r"\x1b\[[0-?]*[ -/]*[@A-Z\[\\\]^_`a-ln-~]")


def render_toolbar(content: AnyFormattedText) -> str:
    """Render a toolbar's content as text with ANSI style sequences, which is what gets sent to the Textual application.

    prompt-toolkit does the rendering, so everything ``get_bottom_toolbar()`` is allowed to return is understood,
    and style classes mean what cmd2's theme says they mean.

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
    # cmd2's theme over prompt-toolkit's default style, which is how a prompt-toolkit application combines them
    style = merge_styles([default_ui_style(), DynamicStyle(get_pt_theme)])
    print_formatted_text(output, to_formatted_text(content), style, color_depth=ColorDepth.TRUE_COLOR)
    # The renderer also sets up the terminal around the text, which is none of the Textual application's business
    return NOT_A_STYLE.sub("", stream.getvalue()).replace("\r\n", "\n")


class ToolbarReporter:
    """Sends a toolbar's content to the Textual application whenever it changes, from a thread of its own."""

    def __init__(self, get_toolbar: Callable[[], AnyFormattedText], socket_path: str, interval: float) -> None:
        """Connect to the Textual application.

        :param get_toolbar: returns the toolbar's content, like ``cmd2.Cmd.get_bottom_toolbar()``
        :param socket_path: the Unix socket which the Textual application listens on
        :param interval: seconds between looks at the toolbar's content
        """
        self._get_toolbar = get_toolbar
        self._interval = interval
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(socket_path)
        self._wake = threading.Event()
        self._stopping = False
        self._last_sent: str | None = None
        self._thread = threading.Thread(target=self._run, name="toolbar-reporter", daemon=True)

    def start(self) -> None:
        """Send the toolbar once, then keep it up to date."""
        self._report()
        self._thread.start()

    def poke(self) -> None:
        """Look at the toolbar's content now rather than at the next interval, because something has changed."""
        self._wake.set()

    def stop(self) -> None:
        """Stop reporting and close the connection."""
        self._stopping = True
        self._wake.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
        self._socket.close()

    def _run(self) -> None:
        while not self._stopping:
            self._wake.wait(self._interval)
            self._wake.clear()
            if self._stopping or not self._report():
                return

    def _report(self) -> bool:
        """Send the toolbar's content if it has changed.

        :return: False if the Textual application has gone away
        """
        try:
            rendered = render_toolbar(self._get_toolbar())
        except Exception:  # noqa: BLE001
            # This runs application code on a thread nobody is watching. Keep showing the last good toolbar.
            return True
        if rendered == self._last_sent:
            return True
        try:
            # One JSON document per line
            self._socket.sendall(json.dumps({"toolbar": rendered}).encode() + b"\n")
        except OSError:
            return False
        self._last_sent = rendered
        return True


class ToolbarApp(cmd2.Cmd):
    """A cmd2 application with a bottom toolbar which says what it is doing."""

    def __init__(self, toolbar_socket: str | None) -> None:
        """Initialize the cmd2 application.

        :param toolbar_socket: the Unix socket of the Textual application which draws the toolbar, or None if this
                               application isn't running inside one. Then prompt-toolkit draws the toolbar as usual,
                               which means only while the prompt is on the screen.
        """
        refresh_interval = 0.5
        super().__init__(
            allow_cli_args=False,
            # Inside the Textual application, don't have prompt-toolkit draw a second toolbar in the terminal pane
            enable_bottom_toolbar=toolbar_socket is None,
            refresh_interval=refresh_interval,
        )
        self.prompt = "toolbar-demo> "
        self._commands_run = 0
        self._running_command = ""

        self._reporter: ToolbarReporter | None = None
        if toolbar_socket is not None:
            self._reporter = ToolbarReporter(self.get_bottom_toolbar, toolbar_socket, refresh_interval)

        self.register_postparsing_hook(self._on_command_start)
        self.register_cmdfinalization_hook(self._on_command_end)

    def get_bottom_toolbar(self) -> AnyFormattedText:
        """Return the toolbar's content. Inside the Textual application this is called on the reporter's thread."""
        if self._running_command:
            state = ("fg:ansiyellow bold", f"running {self._running_command}")
        else:
            state = ("fg:ansigreen bold", "idle")
        return [("", " "), state, ("", f"  |  commands run: {self._commands_run}  |  {time.strftime('%H:%M:%S')} ")]

    def preloop(self) -> None:
        """Start sending the toolbar before the first prompt."""
        if self._reporter is not None:
            self._reporter.start()

    def postloop(self) -> None:
        """Stop sending the toolbar once the command loop has ended."""
        if self._reporter is not None:
            self._reporter.stop()

    def _on_command_start(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Note which command is about to run, and show it in the toolbar without waiting for the next interval."""
        self._running_command = data.statement.command
        if self._reporter is not None:
            self._reporter.poke()
        return data

    def _on_command_end(self, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
        """Note that the command is done, even when it failed."""
        # Finalization hooks also run for blank lines, comments, and syntax errors, which never became a statement
        if data.statement is not None:
            self._commands_run += 1
        self._running_command = ""
        if self._reporter is not None:
            self._reporter.poke()
        return data

    @cmd2.with_argument_list
    def do_slow(self, args: list[str]) -> None:
        """Print a line every quarter of a second: slow [COUNT]."""
        for number in range(int(args[0]) if args else 12):
            self.poutput(f"line {number}")
            time.sleep(0.25)
        self.poutput("slow done")

    @cmd2.with_argument_list
    def do_burst(self, args: list[str]) -> None:
        """Print numbered lines with an optional pause between them: burst [COUNT [DELAY_MS]]."""
        count = int(args[0]) if args else 1000
        delay = int(args[1]) / 1000 if len(args) > 1 else 0
        started = time.perf_counter()
        for number in range(count):
            self.poutput(f"burst {number}")
            if delay:
                time.sleep(delay)
        self.poutput(f"burst done in {time.perf_counter() - started:.2f} s")

    @cmd2.with_argument_list
    def do_page(self, args: list[str]) -> None:
        """Show numbered rows in a pager: page [COUNT]."""
        self.ppaged("\n".join(f"row {number}" for number in range(int(args[0]) if args else 300)))

    def do_ask(self, _: cmd2.Statement) -> None:
        """Ask for a line of input in the middle of a command."""
        self.poutput(f"got {self.read_input('Value: ')}")

    def do_fail(self, _: cmd2.Statement) -> bool:
        """End the application with exit code 3."""
        self.exit_code = 3
        return True


def run_textual_app() -> int:
    """Run the Textual application with the cmd2 application in a terminal pane and its toolbar below it.

    Textual is imported here rather than at the top of the module so the cmd2 application can run without it.

    :return: the exit code of the cmd2 application
    """
    import asyncio

    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.message import Message
    from textual.widgets import Static
    from textual_tty import Terminal

    class ToolbarChanged(Message):
        """The cmd2 application sent new content for its toolbar."""

        def __init__(self, rendered: str) -> None:
            self.rendered = rendered
            super().__init__()

    class ToolbarHost(App[None]):
        """A Textual application which is nothing but a terminal pane running cmd2 and a toolbar below it."""

        CSS = """
        #cmd2 {
            height: 1fr;
        }
        #toolbar {
            dock: bottom;
            /* As tall as its content, so a toolbar of two rows takes two rows from the terminal pane */
            height: auto;
            min-height: 1;
            background: $foreground;
            color: $background;
        }
        """
        # All there is to see is the cmd2 application, so there is nothing for a command palette to do
        ENABLE_COMMAND_PALETTE = False

        def __init__(self, cmd2_command: list[str], listener: socket.socket) -> None:
            """Initialize the Textual application.

            :param cmd2_command: the command which runs the cmd2 application
            :param listener: the listening Unix socket which the cmd2 application sends its toolbar to
            """
            super().__init__()
            self.cmd2_exit_code = 0
            self._cmd2_command = cmd2_command
            self._listener = listener
            self._server: asyncio.Server | None = None

        def compose(self) -> ComposeResult:
            """Create the layout: the terminal running cmd2, and the toolbar docked below it."""
            yield Terminal(command=self._cmd2_command, id="cmd2")
            yield Static("", id="toolbar")

        async def on_mount(self) -> None:
            """Start reading the toolbar, and give the keyboard focus to the terminal."""
            self._server = await asyncio.start_unix_server(self._read_toolbar, sock=self._listener)
            self.query_one(Terminal).focus()

        async def on_unmount(self) -> None:
            """Stop accepting connections."""
            if self._server is not None:
                self._server.close()

        async def _read_toolbar(self, reader: asyncio.StreamReader, _writer: asyncio.StreamWriter) -> None:
            """Read the toolbar from the cmd2 application, which sends one JSON document per line."""
            while line := await reader.readline():
                # Ignore anything which isn't a valid document rather than letting it crash the application
                with contextlib.suppress(TypeError, ValueError, RecursionError):
                    document = json.loads(line)
                    if isinstance(document, dict) and isinstance(document.get("toolbar"), str):
                        self.post_message(ToolbarChanged(document["toolbar"]))

        def on_toolbar_changed(self, message: ToolbarChanged) -> None:
            """Show the new toolbar. The text arrived with ANSI style sequences, which Rich understands."""
            self.query_one("#toolbar", Static).update(Text.from_ansi(message.rendered))

        def on_terminal_process_exited(self, event: Terminal.ProcessExited) -> None:
            """Exit when the cmd2 application exits, for example due to the quit command."""
            if event.exit_code == 0:
                self.exit()
                return
            if event.exit_code < 0:
                # The exit code of a process killed by a signal is the negated signal number. Shells report 128 + signal.
                outcome = f"was killed by signal {-event.exit_code}"
                self.cmd2_exit_code = 128 - event.exit_code
            else:
                outcome = f"exited with code {event.exit_code}"
                self.cmd2_exit_code = event.exit_code
            # Keep the terminal on the screen so the cmd2 application's error output, like a traceback, can be read
            self.query_one("#toolbar", Static).update(Text(f" The cmd2 application {outcome}. Press Ctrl-Q to close. "))

        async def action_quit(self) -> None:
            """Exit with the cmd2 application's exit code, so the shell can tell whether it failed."""
            self.exit(return_code=self.cmd2_exit_code)

    # A Unix socket's path is limited to about a hundred bytes, so make a short one
    directory = tempfile.mkdtemp(prefix="cmd2-")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        socket_path = f"{directory}/toolbar.sock"
        # Listen before the cmd2 application is started, so its connection is never refused
        listener.bind(socket_path)
        listener.listen(1)
        app = ToolbarHost([sys.executable, __file__, "--cmd2-only", "--toolbar-socket", socket_path], listener)
        app.run()
        return app.return_code or app.cmd2_exit_code
    finally:
        listener.close()
        shutil.rmtree(directory, ignore_errors=True)


def main() -> int:
    """Run the Textual application, or just the cmd2 application if --cmd2-only is given."""
    parser = argparse.ArgumentParser(description="Run a cmd2 application whose bottom toolbar is drawn by Textual.")
    parser.add_argument("--cmd2-only", action="store_true", help="run just the cmd2 application, without Textual")
    parser.add_argument(
        "--toolbar-socket",
        metavar="PATH",
        help="with --cmd2-only, send the toolbar to this Unix socket, which the Textual application listens on",
    )
    cli_args = parser.parse_args()
    if cli_args.toolbar_socket and not cli_args.cmd2_only:
        parser.error("--toolbar-socket can only be used with --cmd2-only")

    if cli_args.cmd2_only:
        return ToolbarApp(toolbar_socket=cli_args.toolbar_socket).cmdloop()
    if sys.platform == "win32":
        parser.error("the Textual application requires a POSIX system, use --cmd2-only to run just the cmd2 application")
    return run_textual_app()


if __name__ == "__main__":
    sys.exit(main())
