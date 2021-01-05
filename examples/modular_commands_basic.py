#!/usr/bin/env python3
# coding=utf-8
"""
Simple example demonstrating basic CommandSet usage.
"""

import cmd2
from cmd2 import (
    CommandSet,
    with_default_category,
)


@with_default_category('My Category')
class AutoLoadCommandSet(CommandSet):
    def __init__(self):
        super().__init__()

    def do_hello(self, _: cmd2.Statement):
        self._cmd.poutput('Hello')

    def do_world(self, _: cmd2.Statement):
        self._cmd.poutput('World')


class ExampleApp(cmd2.Cmd):
    """
    CommandSets are automatically loaded. Nothing needs to be done.
    """

    def __init__(self):
        super(ExampleApp, self).__init__()

    def do_something(self, arg):
        self.poutput('this is the something command')


if __name__ == '__main__':
    app = ExampleApp()
    app.cmdloop()
