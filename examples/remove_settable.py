#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2 demonstrating how to remove one of the built-in runtime settable parameters.
"""
import cmd2


class MyApp(cmd2.Cmd):

    def __init__(self):
        super().__init__()
        self.settables.pop('debug')


if __name__ == '__main__':
    import sys
    c = MyApp()
    sys.exit(c.cmdloop())
