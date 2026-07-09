#!/usr/bin/env python
"""A simple example demonstrating an application that asynchronously prints alerts, updates the prompt
and changes the window title.
"""

import secrets
import threading
import time
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import cmd2
from cmd2 import (
    Color,
    stylize,
)


def get_alerts() -> list[tuple[Any, bool]]:
    """Return a list of (alert_msg, soft_wrap) tuples."""
    table = Table("Command", "Description", title="Quick Help")
    table.add_row("start_alerts", "Start the async alert generator")
    table.add_row("stop_alerts", "Stop the async alert generator")
    table.add_row("help", "Show help menu")

    # Set soft_wrap to False when printing structured Renderables like Tables, Panels, or Columns
    # to ensure they render as expected. For example, when soft_wrap is True, Panels truncate
    # text which is wider than the terminal.
    return [
        (Text("Watch as this application prints alerts asynchronously!", style="bold bright_cyan"), True),
        ("Notice how alerts don't interfere with your typing or cursor location.", True),
        (
            Panel(
                "This message is wrapped in a Rich Panel!",
                title="System Alert",
                border_style="bright_blue",
                expand=False,
            ),
            False,
        ),
        (table, False),
        ("You can stop and start the alerts by typing stop_alerts and start_alerts.", True),
    ]


class AlerterApp(cmd2.Cmd):
    """An app that shows off async_alert() and async_update_prompt()."""

    def __init__(self) -> None:
        """Initializer."""
        super().__init__()

        self.prompt = "(APR)> "

        # The thread that will asynchronously alert the user of events
        self._stop_event = threading.Event()
        self._add_alert_thread = threading.Thread()
        self._alert_count = 0

        # Create some hooks to handle the starting and stopping of our thread
        self.register_preloop_hook(self._preloop_hook)
        self.register_postloop_hook(self._postloop_hook)

        # Create an instance of SystemRandom
        self._secure_generator = secrets.SystemRandom()

    def _preloop_hook(self) -> None:
        """Start the alerter thread."""
        self._stop_event.clear()
        self._add_alert_thread = threading.Thread(name="alerter", target=self._add_alerts_func)
        self._add_alert_thread.start()

    def _postloop_hook(self) -> None:
        """Stop the alerter thread."""
        self._stop_event.set()
        if self._add_alert_thread.is_alive():
            self._add_alert_thread.join()

    def do_start_alerts(self, _: cmd2.Statement) -> None:
        """Start the alerter thread."""
        if self._add_alert_thread.is_alive():
            print("The alert thread is already started")
        else:
            self._stop_event.clear()
            self._add_alert_thread = threading.Thread(name="alerter", target=self._add_alerts_func)
            self._add_alert_thread.start()

    def do_stop_alerts(self, _: cmd2.Statement) -> None:
        """Stop the alerter thread."""
        self._stop_event.set()
        if self._add_alert_thread.is_alive():
            self._add_alert_thread.join()
        else:
            print("The alert thread is already stopped")

    def _build_colored_prompt(self) -> str:
        """Randomly build a colored prompt.

        :return: the new prompt.
        """
        rand_num = self._secure_generator.randint(1, 6)

        status_color = Color.DEFAULT

        if rand_num == 1:
            status_color = Color.BRIGHT_RED
        elif rand_num == 2:
            status_color = Color.BRIGHT_YELLOW
        elif rand_num == 3:
            status_color = Color.CYAN
        elif rand_num == 4:
            status_color = Color.BRIGHT_GREEN
        elif rand_num == 5:
            status_color = Color.BRIGHT_BLUE

        return stylize(self.visible_prompt, style=status_color)

    def _add_alerts_func(self) -> None:
        """Print alerts and update the prompt any time the prompt is showing."""
        self._alert_count = 0

        alerts = get_alerts()
        alert_index = 0
        last_alert_time = 0.0

        while not self._stop_event.is_set():
            cur_time = time.monotonic()
            alert_msg = None
            soft_wrap = True

            # Trigger the next alert every 4 seconds
            if cur_time - last_alert_time >= 4.0:
                alert_msg, soft_wrap = alerts[alert_index]
                alert_index = (alert_index + 1) % len(alerts)
                self._alert_count += 1
                last_alert_time = cur_time

            # Build a new prompt (color changes randomly)
            new_prompt = self._build_colored_prompt()

            # Check if we have an alert to print
            if alert_msg is not None:
                # Wrap the alert message and an empty string in a Rich Group.
                # This is a clean way to append a blank line after any RenderableType
                # (strings, panels, tables, etc.) for visual separation.
                self.add_alert(
                    msg=Group(alert_msg, ""),
                    soft_wrap=soft_wrap,
                    prompt=new_prompt,
                )

                new_title = f"Alerts Printed: {self._alert_count}"
                self.set_window_title(new_title)

            # Otherwise, check if the prompt needs to be updated or refreshed
            elif self.prompt != new_prompt:
                self.add_alert(prompt=new_prompt)

            self._stop_event.wait(1.0)


if __name__ == "__main__":
    import sys

    app = AlerterApp()
    app.set_window_title("Asynchronous Printer Test")
    sys.exit(app.cmdloop())
