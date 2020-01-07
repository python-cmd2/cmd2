#!/usr/bin/env python3
# coding=utf-8
"""A simple example demonstrating how do_* commands can be created in a loop.
"""
import functools

import cmd2
from cmd2.constants import COMMAND_FUNC_PREFIX, HELP_FUNC_PREFIX

COMMAND_LIST = ['foo', 'bar']
CATEGORY = 'Dynamic Commands'


class CommandsInLoop(cmd2.Cmd):
    """Example of dynamically adding do_* commands."""
    def __init__(self):
        # Add dynamic commands before calling cmd2.Cmd's init since it validates command names
        for command in COMMAND_LIST:
            # Create command function and add help category to it
            cmd_func = functools.partial(self.send_text, text=command)
            cmd2.categorize(cmd_func, CATEGORY)

            # Add command function to CLI object
            cmd_func_name = COMMAND_FUNC_PREFIX + command
            setattr(self, cmd_func_name, cmd_func)

            # Add help function to CLI object
            help_func = functools.partial(self.text_help, text=command)
            help_func_name = HELP_FUNC_PREFIX + command
            setattr(self, help_func_name, help_func)

        super().__init__(use_ipython=True)

    def send_text(self, args: cmd2.Statement, *, text: str):
        """Simulate sending text to a server and printing the response."""
        self.poutput(text.capitalize())

    def text_help(self, *, text: str):
        """Deal with printing help for the dynamically added commands."""
        self.poutput("Simulate sending {!r} to a server and printing the response".format(text))


if __name__ == '__main__':
    app = CommandsInLoop()
    app.cmdloop()
