#!/usr/bin/env python
"""A sample application for cmd2 demonstrating how to remove one of the built-in runtime settable parameters."""

import cmd2


class MyApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.remove_settable('debug')


if __name__ == '__main__':
    import sys

    c = MyApp()
    sys.exit(c.cmdloop())
