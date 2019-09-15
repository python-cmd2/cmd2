#!/usr/bin/env python3
# coding=utf-8
"""A simple example demonstrating how do_* commands can be created in a loop.
"""
import functools
import cmd2
COMMAND_LIST = ['foo', 'bar', 'baz']


class CommandsInLoop(cmd2.Cmd):
    """Example of dynamically adding do_* commands."""
    def __init__(self):
        super().__init__(use_ipython=True)

    def send_text(self, args: cmd2.Statement, *, text: str):
        """Simulate sending text to a server and printing the response."""
        self.poutput(text.capitalize())

    def text_help(self, *, text: str):
        """Deal with printing help for the dynamically added commands."""
        self.poutput("Simulate sending {!r} to a server and printing the response".format(text))


for command in COMMAND_LIST:
    setattr(CommandsInLoop, 'do_{}'.format(command), functools.partialmethod(CommandsInLoop.send_text, text=command))
    setattr(CommandsInLoop, 'help_{}'.format(command), functools.partialmethod(CommandsInLoop.text_help, text=command))


if __name__ == '__main__':
    app = CommandsInLoop()
    app.cmdloop()
