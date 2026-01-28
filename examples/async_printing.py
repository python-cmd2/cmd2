#!/usr/bin/env python
"""A simple example demonstrating an application that asynchronously prints alerts, updates the prompt
and changes the window title.
"""

import asyncio
import contextlib
import random
import time

import cmd2
from cmd2 import (
    Color,
    stylize,
)

ALERTS = [
    "Watch as this application prints alerts and updates the prompt",
    "This will only happen when the prompt is present",
    "Notice how it doesn't interfere with your typing or cursor location",
    "Go ahead and type some stuff and move the cursor throughout the line",
    "Keep typing...",
    "Move that cursor...",
    "Pretty seamless, eh?",
    "Feedback can also be given in the window title. Notice the alert count up there?",
    "You can stop and start the alerts by typing stop_alerts and start_alerts",
    "This demo will now continue to print alerts at random intervals",
]


class AlerterApp(cmd2.Cmd):
    """An app that shows off async_alert() and async_update_prompt()."""

    def __init__(self, *args, **kwargs) -> None:
        """Initializer."""
        super().__init__(*args, **kwargs)

        self.prompt = "(APR)> "

        # The task that will asynchronously alert the user of events
        self._alerter_task: asyncio.Task | None = None
        self._alerts_enabled = True
        self._alert_count = 0
        self._next_alert_time = 0

        # Register hook to stop alerts when the command loop finishes
        self.register_postloop_hook(self._postloop_hook)

    def pre_prompt(self) -> None:
        """Start the alerter task if enabled.
        This is called after the prompt event loop has started, so create_background_task works.
        """
        if self._alerts_enabled:
            self._start_alerter_task()

    def _postloop_hook(self) -> None:
        """Stops the alerter task."""
        self._cancel_alerter_task()

    def do_start_alerts(self, _) -> None:
        """Starts the alerter task."""
        if self._alerts_enabled:
            print("The alert task is already started")
        else:
            self._alerts_enabled = True
            # Task will be started in pre_prompt at next prompt

    def do_stop_alerts(self, _) -> None:
        """Stops the alerter task."""
        if not self._alerts_enabled:
            print("The alert task is already stopped")
        else:
            self._alerts_enabled = False
            self._cancel_alerter_task()

    def _start_alerter_task(self) -> None:
        """Start the alerter task if it's not running."""
        if self._alerter_task is not None and not self._alerter_task.done():
            return

        # self.session.app is the prompt_toolkit Application.
        # create_background_task creates a task that runs on the same loop as the app.
        with contextlib.suppress(RuntimeError):
            self._alerter_task = self.session.app.create_background_task(self._alerter())

    def _cancel_alerter_task(self) -> None:
        """Cancel the alerter task."""
        if self._alerter_task is not None:
            self._alerter_task.cancel()
            self._alerter_task = None

    def _get_alerts(self) -> list[str]:
        """Reports alerts
        :return: the list of alerts.
        """
        cur_time = time.monotonic()
        if cur_time < self._next_alert_time:
            return []

        alerts = []

        if self._alert_count < len(ALERTS):
            alerts.append(ALERTS[self._alert_count])
            self._alert_count += 1
            self._next_alert_time = cur_time + 4

        else:
            rand_num = random.randint(1, 20)
            if rand_num > 2:
                return []

            for _ in range(rand_num):
                self._alert_count += 1
                alerts.append(f"Alert {self._alert_count}")

            self._next_alert_time = 0

        return alerts

    def _generate_alert_str(self) -> str:
        """Combines alerts into one string that can be printed to the terminal
        :return: the alert string.
        """
        alert_str = ''
        alerts = self._get_alerts()

        longest_alert = max(ALERTS, key=len)
        num_asterisks = len(longest_alert) + 8

        for i, cur_alert in enumerate(alerts):
            # Use padding to center the alert
            padding = ' ' * int((num_asterisks - len(cur_alert)) / 2)

            if i > 0:
                alert_str += '\n'
            alert_str += '*' * num_asterisks + '\n'
            alert_str += padding + cur_alert + padding + '\n'
            alert_str += '*' * num_asterisks + '\n'

        return alert_str

    def _generate_colored_prompt(self) -> str:
        """Randomly generates a colored prompt
        :return: the new prompt.
        """
        rand_num = random.randint(1, 20)

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

    async def _alerter(self) -> None:
        """Prints alerts and updates the prompt any time the prompt is showing."""
        self._alert_count = 0
        self._next_alert_time = 0

        try:
            while True:
                # Get any alerts that need to be printed
                alert_str = self._generate_alert_str()

                # Generate a new prompt
                new_prompt = self._generate_colored_prompt()

                # Check if we have alerts to print
                if alert_str:
                    # We are running on the main loop, so we can print directly.
                    # patch_stdout (active during read_input) handles the output.
                    print(alert_str)

                    self.prompt = new_prompt
                    new_title = f"Alerts Printed: {self._alert_count}"
                    self.set_window_title(new_title)
                    self.session.app.invalidate()

                # Otherwise check if the prompt needs to be updated or refreshed
                elif self.prompt != new_prompt:
                    self.prompt = new_prompt
                    self.session.app.invalidate()

                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass


if __name__ == '__main__':
    import sys

    app = AlerterApp()
    app.set_window_title("Asynchronous Printer Test")
    sys.exit(app.cmdloop())
