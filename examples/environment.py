#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2 demonstrating customized environment parameters
"""

import cmd2


class EnvironmentApp(cmd2.Cmd):
    """ Example cmd2 application. """

    degrees_c = 22
    sunny = False

    def __init__(self):
        self.settable.update({'degrees_c': 'Temperature in Celsius'})
        self.settable.update({'sunny': 'Is it sunny outside?'})
        super().__init__()

    def do_sunbathe(self, arg):
        if self.degrees_c < 20:
            result = "It's {} C - are you a penguin?".format(self.degrees_c)
        elif not self.sunny:
            result = 'Too dim.'
        else:
            result = 'UV is bad for your skin.'
        self.poutput(result)

    def _onchange_degrees_c(self, old, new):
        # if it's over 40C, it's gotta be sunny, right?
        if new > 40:
            self.sunny = True


if __name__ == '__main__':
    c = EnvironmentApp()
    c.cmdloop()
