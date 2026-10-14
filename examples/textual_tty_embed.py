#!/usr/bin/env python3
"""Embed a cmd2 application in a Textual application using textual-tty.

The Textual application shows the cmd2 application in a terminal pane on the left. A status panel on the
right is a regular Textual widget, so it can show much richer, realtime information than a bottom toolbar.
The panel has a wall clock which is updated by Textual and the state of the cmd2 application: whether it
is idle or running a command, how many commands it has run, and what the last one was.

How it works:
  - [textual-tty](https://github.com/ttygroup/textual-tty) provides the ``Terminal`` widget, a terminal
    emulator (built on bittty) which runs a child process attached to a pseudo-terminal.
  - The child process is simply this script run with ``--cmd2-only``, so the cmd2 application is completely
    unaware that it is being embedded. It is a normal cmd2 application which uses prompt-toolkit.
  - To report its state to the host, the cmd2 application calls ``cmd2.Cmd.set_window_title()`` with a JSON
    document from precmd and command finalization hooks. The ``Terminal`` widget turns the title change
    into a ``Terminal.TitleChanged`` message which the Textual application uses to update the status panel.
    This uses only the pseudo-terminal, so there are no sockets, files, or threads to manage.

Neither textual nor textual-tty are dependencies of cmd2. To run this example from a cmd2 checkout use:

    uv run --with textual-tty examples/textual_tty_embed.py

or install the extra packages into your own environment with ``pip install textual-tty`` and then run
``python examples/textual_tty_embed.py``. This requires a POSIX terminal or Windows with pywinpty
(which textual-tty installs for you).

The cmd2 application can also be run on its own, without Textual:

    python examples/textual_tty_embed.py --cmd2-only

Use the ``quit`` command in the embedded cmd2 application, or press Ctrl-Q, to exit.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any

from prompt_toolkit.application import get_app_session
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static
from textual_tty import Terminal

import cmd2

# Prefix which marks a window title as a status update from the cmd2 application
STATUS_PREFIX = "cmd2-status:"


class StatusApp(cmd2.Cmd):
    """A small cmd2 application which reports its state to whatever terminal it is running in."""

    def __init__(self) -> None:
        """Initialize the cmd2 application and register the hooks which report its status."""
        super().__init__(allow_cli_args=False)
        self.prompt = "status-demo> "
        self.intro = "Run a few commands and watch the status panel next to this terminal."

        self._commands_run = 0
        self._last_command = ""
        self._last_duration = 0.0
        self._command_started = 0.0

        self.register_precmd_hook(self._on_command_start)
        self.register_cmdfinalization_hook(self._on_command_end)

    def _report_status(self, state: str) -> None:
        """Send the application's current state to the terminal as a window title."""
        status = {
            "state": state,
            "commands_run": self._commands_run,
            "last_command": self._last_command,
            "last_duration": self._last_duration,
        }
        self.set_window_title(STATUS_PREFIX + json.dumps(status))
        # prompt-toolkit buffers its output, so flush it or the "running" state would only appear after the command ends
        get_app_session().output.flush()

    def preloop(self) -> None:
        """Report the initial status before the first prompt."""
        self._report_status("idle")

    def _on_command_start(self, data: cmd2.plugin.PrecommandData) -> cmd2.plugin.PrecommandData:
        """Report that a command is about to run."""
        self._last_command = data.statement.command or ""
        self._command_started = time.monotonic()
        self._report_status("running")
        return data

    def _on_command_end(self, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
        """Report that the command is done, even when it failed."""
        self._commands_run += 1
        self._last_duration = time.monotonic() - self._command_started
        self._report_status("idle")
        return data

    @cmd2.with_argument_list
    def do_greet(self, args: list[str]) -> None:
        """Greet someone."""
        self.poutput(f"Hello, {' '.join(args) or 'world'}!")

    @cmd2.with_argument_list
    def do_slow(self, args: list[str]) -> None:
        """Run for a number of seconds (default 3) so the status panel can be seen in the running state."""
        try:
            seconds = float(args[0]) if args else 3.0
        except ValueError:
            self.perror(f"Not a number: {args[0]}")
            return
        self.poutput(f"Working for {seconds:g} seconds...")
        time.sleep(seconds)
        self.poutput("Done.")


class ClockPanel(Static):
    """The time of day, which is updated by Textual and has nothing to do with the cmd2 application."""

    def on_mount(self) -> None:
        """Start updating the clock every second."""
        self.update_clock()
        self.set_interval(1, self.update_clock)

    def update_clock(self) -> None:
        """Show the current time."""
        self.update(f"[b]Clock[/b]\n{datetime.now().astimezone():%H:%M:%S %Z}")


class StatusPanel(Static):
    """The state of the embedded cmd2 application as last reported through its window title."""

    state: reactive[str] = reactive("starting")
    commands_run: reactive[int] = reactive(0)
    last_command: reactive[str] = reactive("")
    last_duration: reactive[float] = reactive(0.0)

    def render(self) -> str:
        """Render the panel from the reactive attributes. Textual refreshes it when any of them change."""
        color = "green" if self.state == "idle" else "yellow"
        return (
            "[b]cmd2 status[/b]\n"
            f"State: [{color}]{self.state}[/{color}]\n"
            f"Commands run: {self.commands_run}\n"
            f"Last command: {self.last_command or '-'}\n"
            f"Last duration: {self.last_duration:.2f}s"
        )

    def apply(self, status: dict[str, Any]) -> None:
        """Update the panel from a status document sent by the cmd2 application."""
        self.state = str(status.get("state", "unknown"))
        self.commands_run = int(status.get("commands_run", 0))
        self.last_command = str(status.get("last_command", ""))
        self.last_duration = float(status.get("last_duration", 0.0))


class Cmd2InTextual(App[None]):
    """A Textual application with a cmd2 application in a terminal pane and a status panel beside it."""

    TITLE = "cmd2 inside Textual"

    CSS = """
    #cmd2 {
        width: 2fr;
        border: round $primary;
    }
    #sidebar {
        width: 1fr;
    }
    #sidebar Static {
        border: round $secondary;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    # Priority bindings are needed because the focused Terminal sends every key press to the cmd2 application
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", priority=True)]

    def compose(self) -> ComposeResult:
        """Create the layout: the terminal running cmd2 on the left and the status panels on the right."""
        yield Header()
        with Horizontal():
            yield Terminal(command=[sys.executable, __file__, "--cmd2-only"], id="cmd2")
            with Vertical(id="sidebar"):
                yield StatusPanel(id="status")
                yield ClockPanel(id="clock")
        yield Footer()

    def on_mount(self) -> None:
        """Give the keyboard focus to the terminal so typing goes to the cmd2 application."""
        self.query_one(Terminal).focus()

    def on_terminal_title_changed(self, event: Terminal.TitleChanged) -> None:
        """Update the status panel when the cmd2 application reports its status."""
        if not event.title.startswith(STATUS_PREFIX):
            return
        try:
            status = json.loads(event.title.removeprefix(STATUS_PREFIX))
        except json.JSONDecodeError:
            return
        self.query_one(StatusPanel).apply(status)

    def on_terminal_process_exited(self, event: Terminal.ProcessExited) -> None:
        """Exit when the cmd2 application exits, for example due to the quit command."""
        self.exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a cmd2 application embedded in a Textual application.")
    parser.add_argument("--cmd2-only", action="store_true", help="run just the cmd2 application, without Textual")
    cli_args = parser.parse_args()

    if cli_args.cmd2_only:
        sys.exit(StatusApp().cmdloop())
    else:
        Cmd2InTextual().run()
