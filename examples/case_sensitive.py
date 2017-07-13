#!/usr/bin/env python
# coding=utf-8
"""A sample application demonstrating when commands are set to be case sensitive.

By default cmd2 parses commands in a case-insensitive manner.  But this behavior can be changed.
"""

import cmd2


class CaseSensitiveApp(cmd2.Cmd):
    """ Example cmd2 application where commands are case-sensitive."""

    def __init__(self):
        # Set this before calling the super class __init__()
        self.case_insensitive = False

        cmd2.Cmd.__init__(self)

        self.debug = True


if __name__ == '__main__':
    app = CaseSensitiveApp()
    app.cmdloop()
