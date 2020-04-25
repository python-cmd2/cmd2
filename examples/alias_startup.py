#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How to add custom command aliases using the alias command
    2) How to run an initialization script at startup
"""
import os

import cmd2


class AliasAndStartup(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        alias_script = os.path.join(os.path.dirname(__file__), '.cmd2rc')
        super().__init__(startup_script=alias_script)

    def do_nothing(self, args):
        """This command does nothing and produces no output."""
        pass


if __name__ == '__main__':
    import sys
    app = AliasAndStartup()
    sys.exit(app.cmdloop())
