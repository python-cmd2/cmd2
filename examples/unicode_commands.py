#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating support for unicode command names.
"""
import math

import cmd2


class UnicodeApp(cmd2.Cmd):
    """Example cmd2 application with unicode command names."""

    def __init__(self):
        super().__init__()
        self.intro = 'Welcome the Unicode example app. Note the full Unicode support:  😇 💩'

    def do_𝛑print(self, _):
        """This command prints 𝛑 to 5 decimal places."""
        self.poutput("𝛑 = {0:.6}".format(math.pi))

    def do_你好(self, arg):
        """This command says hello in Chinese (Mandarin)."""
        self.poutput("你好 " + arg)


if __name__ == '__main__':
    app = UnicodeApp()
    app.cmdloop()
