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
        self.intro = 'Welcome to MyApp. Note the full Unicode support:  😇 💩'

    def do_𝛑print(self, arg):
        """This command prints 𝛑 to 5 decimal places."""
        print("𝛑 = {0:.6}".format(math.pi))


if __name__ == '__main__':
    app = UnicodeApp()
    app.cmdloop()

