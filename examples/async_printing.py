#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating an application that asynchronously prints alerts and updates the prompt"""

import random
import threading
import time
from typing import List

import cmd2
from colorama import Fore

ALERTS = ["Mail server is down",
          "Blockage detected in sector 4",
          "Ants have overrun the break room",
          "Your next appointment has arrived",
          "Christmas bonuses are cancelled",
          "Mandatory overtime this weekend",
          "Jimmy quit",
          "Jody got married",
          "Is there anyone on board who knows how to fly a plane?",
          "Gentlemen, you can't fight in here. This is the War Room!",
          "Your mom goes to college!"]


def get_alerts() -> List[str]:
    """
    Randomly reports alerts
    :return: the list of alerts
    """
    rand_num = random.randint(1, 20)
    if rand_num > 3:
        return []

    alerts = []
    for i in range(0, rand_num):
        cur_alert = random.choice(ALERTS)
        if cur_alert in alerts:
            i -= 1
        else:
            alerts.append(cur_alert)

    return alerts


def generate_alert_str() -> str:
    """
    Combines alerts into one string that can be printed to the terminal
    :return: the alert string
    """
    alert_str = ''
    alerts = get_alerts()

    longest_alert = max(ALERTS, key=len)
    num_astericks = len(longest_alert) + 8

    for i, cur_alert in enumerate(alerts):
        # Use padding to center the alert
        padding = ' ' * int((num_astericks - len(cur_alert)) / 2)

        if i > 0:
            alert_str += '\n'
        alert_str += '*' * num_astericks + '\n'
        alert_str += padding + cur_alert + padding + '\n'
        alert_str += '*' * num_astericks + '\n'

    return alert_str


class AlerterApp(cmd2.Cmd):
    """ An app that shows off async_alert() and async_update_prompt() """

    def __init__(self, *args, **kwargs) -> None:
        """ Initializer """

        super().__init__(*args, **kwargs)

        self._orig_prompt = "(APR)> "
        self.prompt = self._orig_prompt

        self.intro = "\nWatch as this application prints alerts and updates the prompt.\n"
        self.intro += "This will only happen when the prompt is present. Notice how it doesn't\n"
        self.intro += "interfere with your typing.\n"

        # The thread that will asynchronously alert the user of events
        self._stop_thread = False
        self._alerter_thread = threading.Thread()

        # Create some hooks to handle the starting and stopping of our thread
        self.register_preloop_hook(self._preloop_hook)
        self.register_postloop_hook(self._postloop_hook)

    def _preloop_hook(self) -> None:
        """ Start the alerter thread """

        # This function runs after cmdloop() locks _terminal_lock, which will be locked until the prompt appears.
        # Therefore it is safe to start our thread since there is no risk of it alerting before the prompt is displayed.
        self._stop_thread = False

        self._alerter_thread = threading.Thread(name='alerter', target=self._alerter_thread_func)
        self._alerter_thread.start()

    def _postloop_hook(self) -> None:
        """ Stops the alerter thread """
        self._stop_thread = True
        if self._alerter_thread.is_alive():
            self._alerter_thread.join()

    def _generate_new_prompt(self) -> str:
        """
        Randomly generates a new prompt
        :return: the new prompt
        """
        rand_num = random.randint(1, 20)

        status_color = Fore.RESET

        if rand_num == 1:
            status_color = Fore.LIGHTRED_EX
        elif rand_num == 2:
            status_color = Fore.LIGHTYELLOW_EX
        elif rand_num == 3:
            status_color = Fore.CYAN
        elif rand_num == 4:
            status_color = Fore.LIGHTGREEN_EX
        elif rand_num == 5:
            status_color = Fore.LIGHTBLUE_EX

        return status_color + self._orig_prompt + Fore.RESET

    def _alerter_thread_func(self) -> None:
        """ Prints alerts and updates the prompt any time the prompt is showing """

        while not self._stop_thread:
            # Always acquire _terminal_lock before printing alerts or updating the prompt
            # To keep the app responsive, do not block on this call
            if self._terminal_lock.acquire(blocking=False):

                # Get any alerts that need to be printed
                alert_str = generate_alert_str()

                # Generate a new prompt
                new_prompt = self._generate_new_prompt()

                if alert_str:
                    self._async_alert(alert_str, new_prompt)
                elif new_prompt != self.prompt:
                    self._async_update_prompt(new_prompt)

                # Don't forget to release the lock
                self._terminal_lock.release()

            time.sleep(0.5)


if __name__ == '__main__':
    app = AlerterApp()
    app.set_window_title("Asynchronous Printer Test")
    app.cmdloop()
