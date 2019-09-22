#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating how to remove unused commands.

Commands can be removed from  help menu and tab completion by appending their command name to the hidden_commands list.
These commands will still exist and can be executed and help can be retrieved for them by
name, they just won't clutter the help menu.

Commands can also be removed entirely by using Python's "del".
"""

import cmd2


class RemoveBuiltinCommands(cmd2.Cmd):
    """ Example cmd2 application where we remove some unused built-in commands."""

    def __init__(self):
        super().__init__()

        # To hide commands from displaying in the help menu, add them to the hidden_commands list
        self.hidden_commands.append('py')

        # To remove built-in commands entirely, delete their "do_*" function from the cmd2.Cmd class
        del cmd2.Cmd.do_edit


if __name__ == '__main__':
    import sys
    app = RemoveBuiltinCommands()
    sys.exit(app.cmdloop())
