#!/usr/bin/env python
"""A sample application for cmd2 demonstrating customized environment parameters."""

import cmd2


class EnvironmentApp(cmd2.Cmd):
    """Example cmd2 application."""

    def __init__(self) -> None:
        super().__init__()
        self.degrees_c = 22
        self.sunny = False
        self.add_settable(
            cmd2.Settable('degrees_c', int, 'Temperature in Celsius', self, onchange_cb=self._onchange_degrees_c)
        )
        self.add_settable(cmd2.Settable('sunny', bool, 'Is it sunny outside?', self))

    def do_sunbathe(self, _arg) -> None:
        """Attempt to sunbathe."""
        if self.degrees_c < 20:
            result = f"It's {self.degrees_c} C - are you a penguin?"
        elif not self.sunny:
            result = 'Too dim.'
        else:
            result = 'UV is bad for your skin.'
        self.poutput(result)

    def _onchange_degrees_c(self, _param_name, _old, new) -> None:
        # if it's over 40C, it's gotta be sunny, right?
        if new > 40:
            self.sunny = True


if __name__ == '__main__':
    import sys

    c = EnvironmentApp()
    sys.exit(c.cmdloop())
