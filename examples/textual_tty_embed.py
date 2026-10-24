#!/usr/bin/env python3
"""Embed a cmd2 application in a Textual application using textual-tty.

The Textual application shows the cmd2 application in a terminal pane on the left. A status panel on the
right is a regular Textual widget, so it can show much richer, realtime information than a bottom toolbar.
The panel has a wall clock which is updated by Textual and the state of the cmd2 application: whether it
is idle or running a command, how many commands it has run, and what the last one was.

How it works:
  - [textual-tty](https://github.com/ttygroup/textual-tty) provides the ``Terminal`` widget, a terminal
    emulator (built on bittty) which runs a child process attached to a pseudo-terminal.
  - The child process is simply this script run with ``--cmd2-only --report-status``, so the cmd2 application
    is completely unaware that it is being embedded. It is a normal cmd2 application which uses prompt-toolkit.
  - To report its state to the host, the cmd2 application calls ``cmd2.Cmd.set_window_title()`` with a JSON
    document from postparsing and command finalization hooks. The ``Terminal`` widget turns the title change
    into a ``Terminal.TitleChanged`` message which the Textual application uses to update the status panel.
    This uses only the pseudo-terminal, so there are no sockets, files, or threads to manage.

Neither textual nor textual-tty are dependencies of cmd2. In a cmd2 checkout, textual-tty is part of the
development environment on POSIX systems, so run this example with:

    uv run examples/textual_tty_embed.py

Otherwise, install textual-tty into your own environment with ``pip install textual-tty`` and then run
``python examples/textual_tty_embed.py``. The Textual application requires a POSIX system such as Linux or
macOS, because on Windows textual-tty can only start a program by name and can't pass it arguments.

The cmd2 application can also be run on its own, without Textual, on any platform:

    python examples/textual_tty_embed.py --cmd2-only

Use the ``quit`` command in the embedded cmd2 application, or press Ctrl-Q, to exit.
"""

import argparse
import contextlib
import json
import sys
import time
from datetime import datetime
from typing import Any, ClassVar

from prompt_toolkit.application import get_app_session

import cmd2

# Prefix which marks a window title as a status update from the cmd2 application
STATUS_PREFIX = "cmd2-status:"


class StatusApp(cmd2.Cmd):
    """A small cmd2 application which can report its state to whatever terminal it is running in."""

    def __init__(self, report_status: bool) -> None:
        """Initialize the cmd2 application and register the hooks which track its status.

        :param report_status: if True, report the status through the terminal's window title. Only the Textual
                              application wants this. In a normal terminal it would overwrite the window title.
        """
        super().__init__(allow_cli_args=False)
        self.prompt = "status-demo> "
        if report_status:
            self.intro = "Run a few commands and watch the status panel next to this terminal."

        self._report_status_enabled = report_status
        self._commands_run = 0
        self._running_command = ""
        self._last_command = ""
        self._last_duration = 0.0
        self._command_started = 0.0
        # Commands run by other commands, like run_script and history -r, go through the hooks too. This counts
        # the commands which are running so that only the outermost one is reported.
        self._command_depth = 0

        # Register the postparsing hook before any others. The postparsing hooks stop running when one of them sets
        # stop or raises an exception, but the finalization hooks still run, which would leave the depth unbalanced.
        self.register_postparsing_hook(self._on_command_start)
        self.register_cmdfinalization_hook(self._on_command_end)

    def _report_status(self, state: str) -> None:
        """Send the application's current state to the terminal as a window title."""
        if not self._report_status_enabled:
            return
        status = {
            "state": state,
            "running_command": self._running_command,
            "commands_run": self._commands_run,
            "last_command": self._last_command,
            "last_duration": self._last_duration,
        }
        # If the Textual application exits while a command is running, the terminal is closed before the finalization
        # hook reports the end of the command. Writing to it then fails, which doesn't matter because nobody can see it.
        with contextlib.suppress(OSError):
            self.set_window_title(STATUS_PREFIX + json.dumps(status))
            # prompt-toolkit buffers its output, so flush it or the "running" state would only appear after the command ends
            get_app_session().output.flush()

    def preloop(self) -> None:
        """Report the initial status before the first prompt."""
        self._report_status("idle")

    def _on_command_start(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        """Report that a command is about to run.

        This is a postparsing hook rather than a precmd hook because the finalization hook runs for every statement
        which reaches the postparsing hooks, while precmd hooks are skipped when, for example, redirection fails.
        """
        self._command_depth += 1
        if self._command_depth == 1:
            self._running_command = data.statement.command
            self._command_started = time.monotonic()
            self._report_status("running")
        return data

    def _on_command_end(self, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
        """Report that the command is done, even when it failed."""
        # Finalization hooks also run for blank lines, comments, Ctrl-C at the prompt, and syntax errors. Those
        # never became a statement, so the postparsing hook didn't run for them and there is nothing to report. Also
        # never let the depth go negative, in case a postparsing hook which ran first stopped this hook from running.
        if data.statement is None or self._command_depth == 0:
            return data
        self._command_depth -= 1
        if self._command_depth == 0:
            # Only now does the running command become the last command, so it's never shown next to the duration
            # of the command before it
            self._commands_run += 1
            self._last_command = self._running_command
            self._last_duration = time.monotonic() - self._command_started
            self._running_command = ""
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
        # NaN fails every comparison, so this rejects it along with negative, infinite, and huge values
        if not 0 <= seconds <= 60:
            self.perror(f"Seconds must be from 0 to 60: {args[0]}")
            return
        self.poutput(f"Working for {seconds:g} seconds...")
        time.sleep(seconds)
        self.poutput("Done.")


def run_textual_app() -> int:
    """Run the Textual application with the cmd2 application in a terminal pane and a status panel beside it.

    Textual is imported here rather than at the top of the module so the cmd2 application can run without it.

    :return: the exit code of the cmd2 application, or 0 if the Textual application was quit while it was running
    """
    from textual.app import App, ComposeResult
    from textual.binding import Binding, BindingType
    from textual.containers import Horizontal, Vertical
    from textual.markup import escape
    from textual.reactive import reactive
    from textual.widgets import Footer, Header, Static
    from textual_tty import Terminal

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
        running_command: reactive[str] = reactive("")
        commands_run: reactive[int] = reactive(0)
        last_command: reactive[str] = reactive("")
        last_duration: reactive[float] = reactive(0.0)

        def render(self) -> str:
            """Render the panel from the reactive attributes. Textual refreshes it when any of them change."""
            color = "green" if self.state == "idle" else "yellow"
            state = f"{self.state} {self.running_command}" if self.state == "running" else self.state
            # The strings come from the terminal, so escape them or something like "[/b]" would be read as markup
            return (
                "[b]cmd2 status[/b]\n"
                f"State: [{color}]{escape(state)}[/{color}]\n"
                f"Commands run: {self.commands_run}\n"
                f"Last command: {escape(self.last_command) or '-'}\n"
                f"Last duration: {self.last_duration:.2f}s"
            )

        def apply(self, status: dict[str, Any]) -> None:
            """Update the panel from a status document sent by the cmd2 application.

            :raises TypeError, ValueError, OverflowError: if a value can't be converted to the type it should have
            """
            # Convert every value before setting any of them, so a bad document doesn't half update the panel
            state = str(status.get("state", "unknown"))
            running_command = str(status.get("running_command", ""))
            commands_run = int(status.get("commands_run", 0))
            last_command = str(status.get("last_command", ""))
            last_duration = float(status.get("last_duration", 0.0))

            self.state = state
            self.running_command = running_command
            self.commands_run = commands_run
            self.last_command = last_command
            self.last_duration = last_duration

    class Cmd2InTextual(App[None]):
        """A Textual application with a cmd2 application in a terminal pane and a status panel beside it."""

        TITLE = "cmd2 inside Textual"

        CSS = """
        #cmd2-pane {
            width: 2fr;
            border: round $primary;
        }
        #cmd2 {
            width: 1fr;
            height: 1fr;
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

        # Textual already has a priority binding which makes Ctrl-Q quit even though the focused Terminal sends every
        # other key press to the cmd2 application. It is hidden, so this repeats it only to show Quit in the footer.
        BINDINGS: ClassVar[list[BindingType]] = [Binding("ctrl+q", "quit", "Quit", priority=True)]

        def __init__(self) -> None:
            """Initialize the Textual application."""
            super().__init__()
            self.cmd2_exit_code = 0

        def compose(self) -> ComposeResult:
            """Create the layout: the terminal running cmd2 on the left and the status panels on the right."""
            cmd2_command = [sys.executable, __file__, "--cmd2-only", "--report-status"]
            yield Header()
            with Horizontal():
                # The border is on a container because a Terminal sizes its pseudo-terminal from its outer size, so a
                # border on the Terminal itself makes the cmd2 app draw more rows than are visible and hides its prompt
                with Vertical(id="cmd2-pane"):
                    yield Terminal(command=cmd2_command, id="cmd2")
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
            # Any program run in the terminal, for example by the cmd2 shell command, can set the title. So ignore
            # anything which isn't a valid status document rather than letting it crash the application. Besides
            # json.JSONDecodeError, json.loads raises ValueError for integers with too many digits and RecursionError
            # for documents which are nested too deeply.
            with contextlib.suppress(TypeError, ValueError, OverflowError, RecursionError):
                status = json.loads(event.title.removeprefix(STATUS_PREFIX))
                if isinstance(status, dict):
                    self.query_one(StatusPanel).apply(status)

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
            self.query_one(StatusPanel).state = outcome
            self.notify(f"The cmd2 application {outcome}", severity="error")

        async def action_quit(self) -> None:
            """Exit with the cmd2 application's exit code, so the shell can tell whether it failed."""
            self.exit(return_code=self.cmd2_exit_code)

    app = Cmd2InTextual()
    app.run()
    return app.return_code or 0


def main() -> int:
    """Run the Textual application, or just the cmd2 application if --cmd2-only is given."""
    parser = argparse.ArgumentParser(description="Run a cmd2 application embedded in a Textual application.")
    parser.add_argument("--cmd2-only", action="store_true", help="run just the cmd2 application, without Textual")
    parser.add_argument(
        "--report-status",
        action="store_true",
        help="with --cmd2-only, report the status through the window title, which the Textual application reads",
    )
    cli_args = parser.parse_args()
    if cli_args.report_status and not cli_args.cmd2_only:
        parser.error("--report-status can only be used with --cmd2-only")

    if cli_args.cmd2_only:
        return StatusApp(report_status=cli_args.report_status).cmdloop()
    if sys.platform == "win32":
        parser.error("the Textual application requires a POSIX system, use --cmd2-only to run just the cmd2 application")
    return run_textual_app()


if __name__ == "__main__":
    sys.exit(main())
