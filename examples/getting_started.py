#!/usr/bin/env python3
"""An example cmd2 application demonstrating many common features.

Features demonstrated include all of the following:
 1) Colorizing/stylizing output
 2) Using multiline commands
 3) Persistent history
 4) How to run an initialization script at startup
 5) How to group and categorize commands when displaying them in help
 6) Opting-in to using the ipy command to run an IPython shell
 7) Allowing access to your application in py and ipy
 8) Displaying an intro banner upon starting your application
 9) Using a custom prompt
10) How to make custom attributes settable at runtime.
11) Shortcuts for commands
12) Persistent bottom toolbar with realtime status updates
13) Right prompt which displays contextual information
14) Using a background thread to update the bottom toolbar in an efficient manner
15) Using preloop() and postloop() hooks to start and stop a background thread
"""

import datetime
import pathlib
import sys
import threading

from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import AnyFormattedText
from rich.style import Style

import cmd2
from cmd2 import (
    Color,
    stylize,
)


class BasicApp(cmd2.Cmd):
    """Cmd2 application to demonstrate many common features."""

    DEFAULT_CATEGORY = "My Custom Commands"

    def __init__(self) -> None:
        """Initialize the cmd2 application."""
        # Startup script that defines a couple aliases for running shell commands
        alias_script = pathlib.Path(__file__).absolute().parent / ".cmd2rc"

        # Create a shortcut for one of our commands
        shortcuts = cmd2.DEFAULT_SHORTCUTS
        shortcuts.update({"&": "intro"})

        super().__init__(
            auto_suggest=True,
            enable_bottom_toolbar=True,
            enable_rprompt=True,
            include_ipy=True,
            multiline_commands=["echo"],
            persistent_history_file="cmd2_history.dat",
            refresh_interval=0.5,  # refresh the UI twice a second to keep the bottom toolbar timestamp current
            shortcuts=shortcuts,
            startup_script=str(alias_script),
        )

        # Prints an intro banner once upon application startup
        self.intro = (
            stylize(
                "Welcome to cmd2!",
                style=Style(color=Color.GREEN1, bgcolor=Color.GRAY0, bold=True),
            )
            + " Note the full Unicode support:  😇 💩"
            + " and the persistent bottom bar with realtime status updates!"
        )

        # Show this as the prompt when asking for input
        self.prompt = "myapp> "

        # Used as prompt for multiline commands after the first line
        self.continuation_prompt = "... "

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Color to output text in with echo command
        self.foreground_color = Color.CYAN.value

        # Make echo_fg settable at runtime
        fg_colors = [c.value for c in Color]
        self.add_settable(
            cmd2.Settable(
                "foreground_color",
                str,
                "Foreground color to use with echo command",
                self,
                choices=fg_colors,
            )
        )

        # Initialize background thread state for the bottom toolbar
        self._toolbar_state = {"now": ""}
        self._toolbar_lock = threading.Lock()
        self._stop_thread_event = threading.Event()
        self._toolbar_thread = None

    def _update_toolbar_state(self) -> None:
        """Background thread worker to update toolbar state continuously."""
        while not self._stop_thread_event.is_set():
            # Get the current time in ISO format with 0.01s precision
            dt = datetime.datetime.now(datetime.timezone.utc).astimezone()
            now = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + dt.strftime("%z")

            with self._toolbar_lock:
                self._toolbar_state["now"] = now

            # Sleep to yield CPU, polling 4 times a second
            self._stop_thread_event.wait(0.25)

    def preloop(self) -> None:
        """Hook method executed once when the cmdloop() method is called."""
        super().preloop()
        self._stop_thread_event.clear()
        self._toolbar_thread = threading.Thread(target=self._update_toolbar_state, daemon=True)
        self._toolbar_thread.start()

    def postloop(self) -> None:
        """Hook method executed once when the cmdloop() method is about to return."""
        super().postloop()
        if self._toolbar_thread and self._toolbar_thread.is_alive():
            self._stop_thread_event.set()
            self._toolbar_thread.join()

    def get_bottom_toolbar(self) -> AnyFormattedText:
        left_text = sys.argv[0]

        with self._toolbar_lock:
            now = self._toolbar_state.get("now", "")

        # Fetch the terminal width to calculate padding for right-alignment.
        # If called outside a running app loop (e.g., in unit tests), get_app()
        # safely returns a dummy app with an 80-column fallback.
        cols = get_app().output.get_size().columns
        padding_size = cols - len(left_text) - len(now)
        if padding_size < 1:
            padding_size = 1
        padding = " " * padding_size

        # Return formatted text for prompt-toolkit
        return [
            ("ansigreen", left_text),
            ("", padding),
            ("ansicyan", now),
        ]

    def get_rprompt(self) -> AnyFormattedText:
        current_working_directory = pathlib.Path.cwd()
        style = "bg:ansired fg:ansiwhite"
        text = f"cwd={current_working_directory}"
        return [(style, text)]

    def do_intro(self, _: cmd2.Statement) -> None:
        """Display the intro banner."""
        self.poutput(self.intro)

    def do_echo(self, arg: cmd2.Statement) -> None:
        """Multiline command."""
        self.poutput(
            stylize(
                arg,
                style=Style(color=self.foreground_color),
            )
        )


if __name__ == "__main__":
    app = BasicApp()
    sys.exit(app.cmdloop())
