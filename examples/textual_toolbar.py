#!/usr/bin/env python3
"""PROTOTYPE: a bottom toolbar which stays on the screen while commands run, drawn by Textual.

The toolbar is not drawn by prompt-toolkit, or by cmd2 at all. ``cmd2.textual_toolbar.run()`` starts a
small Textual application which owns the terminal, and runs this program again inside a terminal
emulator widget, with a toolbar widget below it. This program sends the toolbar's content to it.
See ``cmd2/textual_toolbar.py`` for how.

Neither textual nor textual-tty are dependencies of cmd2. In a cmd2 checkout, textual-tty is part of the
development environment on POSIX systems, so run this example with:

    uv run examples/textual_toolbar.py

Things to try: ``slow``, ``burst 2000 1``, ``page 500``, ``ask``, resizing the window while a command
runs, Ctrl-C during ``slow``, and ``quit``. Pass ``--plain`` to run the same application without Textual,
where prompt-toolkit draws the toolbar and it is only there at the prompt.
"""

import os
import sys
import time

import cmd2
from cmd2 import textual_toolbar


class ToolbarDemo(cmd2.Cmd):
    """A cmd2 application with a toolbar which says what it is doing."""

    def __init__(self) -> None:
        super().__init__(allow_cli_args=False, enable_bottom_toolbar=True, refresh_interval=0.5)
        self.prompt = "demo> "
        self.commands_run = 0
        self.running = ""
        self.register_postparsing_hook(self._command_started)
        self.register_cmdfinalization_hook(self._command_finished)

    def _command_started(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
        self.running = data.statement.command
        return data

    def _command_finished(self, data: cmd2.plugin.CommandFinalizationData) -> cmd2.plugin.CommandFinalizationData:
        if data.statement is not None:
            self.commands_run += 1
        self.running = ""
        return data

    def get_bottom_toolbar(self) -> list[tuple[str, str]]:
        """Formatted text, as for prompt-toolkit: a list of (style, text)."""
        state = ("fg:ansiyellow bold", f"running {self.running}") if self.running else ("fg:ansigreen bold", "idle")
        return [
            ("", " "),
            state,
            ("", f"  |  commands run: {self.commands_run}  |  {time.strftime('%H:%M:%S')} "),
        ]

    @cmd2.with_argument_list
    def do_slow(self, args: list[str]) -> None:
        """Print a line every quarter of a second: slow [COUNT]."""
        for number in range(int(args[0]) if args else 12):
            self.poutput(f"line {number}")
            time.sleep(0.25)
        self.poutput("slow done")

    @cmd2.with_argument_list
    def do_burst(self, args: list[str]) -> None:
        """Print numbered lines with a pause between them: burst COUNT [DELAY_MS]."""
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

    def do_fail(self, _: cmd2.Statement) -> None:
        """End the application with exit code 3."""
        self.exit_code = 3
        return True  # type: ignore[return-value]


if __name__ == "__main__":
    if "--plain" in sys.argv:
        # Without the launcher: this is what cmd2 does today.
        os.environ.pop(textual_toolbar.HOST_SOCKET_ENV, None)
        sys.exit(ToolbarDemo().cmdloop())
    sys.exit(textual_toolbar.run(ToolbarDemo))
