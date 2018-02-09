#!/usr/bin/env python
# coding=utf-8
"""This example demonstrates how to enable persistent readline history in your cmd2 application.

This will allow end users of your cmd2-based application to use the arrow keys and Ctrl+r in a manner which persists
across invocations of your cmd2 application.  This can make it much easier for them to use your application.
"""
import cmd2


class Cmd2PersistentHistory(cmd2.Cmd):
    """Basic example of how to enable persistent readline history within your cmd2 app."""
    def __init__(self):
        """"""
        cmd2.Cmd.__init__(self, persistent_history_file='~/.persistent_history.cmd2', persistent_history_length=500)
        self.prompt = 'ph> '

    # ... your class code here ...


if __name__ == '__main__':
    app = Cmd2PersistentHistory()
    app.cmdloop()
