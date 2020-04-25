#!/usr/bin/env python
# coding=utf-8
"""
A simple example demonstrating an application that asynchronously prints alerts, updates the prompt
and changes the window title
"""
import random
import threading
import time
from typing import List

import cmd2
from cmd2 import fg, style

ALERTS = ["Watch as this application prints alerts and updates the prompt",
          "This will only happen when the prompt is present",
          "Notice how it doesn't interfere with your typing or cursor location",
          "Go ahead and type some stuff and move the cursor throughout the line",
          "Keep typing...",
          "Move that cursor...",
          "Pretty seamless, eh?",
          "Feedback can also be given in the window title. Notice the alert count up there?",
          "You can stop and start the alerts by typing stop_alerts and start_alerts",
          "This demo will now continue to print alerts at random intervals"
          ]


class AlerterApp(cmd2.Cmd):
    """ An app that shows off async_alert() and async_update_prompt() """

    def __init__(self, *args, **kwargs) -> None:
        """ Initializer """
        super().__init__(*args, **kwargs)

        self.prompt = "(APR)> "

        # The thread that will asynchronously alert the user of events
        self._stop_thread = False
        self._alerter_thread = threading.Thread()
        self._alert_count = 0
        self._next_alert_time = 0

        # Create some hooks to handle the starting and stopping of our thread
        self.register_preloop_hook(self._preloop_hook)
        self.register_postloop_hook(self._postloop_hook)

    def _preloop_hook(self) -> None:
        """ Start the alerter thread """
        # This runs after cmdloop() acquires self.terminal_lock, which will be locked until the prompt appears.
        # Therefore this is the best place to start the alerter thread since there is no risk of it alerting
        # before the prompt is displayed. You can also start it via a command if its not something that should
        # be running during the entire application. See do_start_alerts().
        self._stop_thread = False

        self._alerter_thread = threading.Thread(name='alerter', target=self._alerter_thread_func)
        self._alerter_thread.start()

    def _postloop_hook(self) -> None:
        """ Stops the alerter thread """

        # After this function returns, cmdloop() releases self.terminal_lock which could make the alerter
        # thread think the prompt is on screen. Therefore this is the best place to stop the alerter thread.
        # You can also stop it via a command. See do_stop_alerts().
        self._stop_thread = True
        if self._alerter_thread.is_alive():
            self._alerter_thread.join()

    def do_start_alerts(self, _):
        """ Starts the alerter thread """
        if self._alerter_thread.is_alive():
            print("The alert thread is already started")
        else:
            self._stop_thread = False
            self._alerter_thread = threading.Thread(name='alerter', target=self._alerter_thread_func)
            self._alerter_thread.start()

    def do_stop_alerts(self, _):
        """ Stops the alerter thread """
        self._stop_thread = True
        if self._alerter_thread.is_alive():
            self._alerter_thread.join()
        else:
            print("The alert thread is already stopped")

    def _get_alerts(self) -> List[str]:
        """
        Reports alerts
        :return: the list of alerts
        """
        global ALERTS

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

            for i in range(0, rand_num):
                self._alert_count += 1
                alerts.append("Alert {}".format(self._alert_count))

            self._next_alert_time = 0

        return alerts

    def _generate_alert_str(self) -> str:
        """
        Combines alerts into one string that can be printed to the terminal
        :return: the alert string
        """
        global ALERTS

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
        """
        Randomly generates a colored prompt
        :return: the new prompt
        """
        rand_num = random.randint(1, 20)

        status_color = fg.reset

        if rand_num == 1:
            status_color = fg.bright_red
        elif rand_num == 2:
            status_color = fg.bright_yellow
        elif rand_num == 3:
            status_color = fg.cyan
        elif rand_num == 4:
            status_color = fg.bright_green
        elif rand_num == 5:
            status_color = fg.bright_blue

        return style(self.visible_prompt, fg=status_color)

    def _alerter_thread_func(self) -> None:
        """ Prints alerts and updates the prompt any time the prompt is showing """

        self._alert_count = 0
        self._next_alert_time = 0

        while not self._stop_thread:
            # Always acquire terminal_lock before printing alerts or updating the prompt
            # To keep the app responsive, do not block on this call
            if self.terminal_lock.acquire(blocking=False):

                # Get any alerts that need to be printed
                alert_str = self._generate_alert_str()

                # Generate a new prompt
                new_prompt = self._generate_colored_prompt()

                # Check if we have alerts to print
                if alert_str:
                    # new_prompt is an optional parameter to async_alert()
                    self.async_alert(alert_str, new_prompt)
                    new_title = "Alerts Printed: {}".format(self._alert_count)
                    self.set_window_title(new_title)

                # No alerts needed to be printed, check if the prompt changed
                elif new_prompt != self.prompt:
                    self.async_update_prompt(new_prompt)

                # Don't forget to release the lock
                self.terminal_lock.release()

            time.sleep(0.5)


if __name__ == '__main__':
    import sys
    app = AlerterApp()
    app.set_window_title("Asynchronous Printer Test")
    sys.exit(app.cmdloop())
