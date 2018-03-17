#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How to add custom command aliases using the alias command
    2) How to load an initialization script at startup
"""
import argparse

import cmd2
import pyparsing

from cmd2 import with_argument_list, with_argparser, with_argparser_and_unknown_args


class AliasAndStartup(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        cmd2.Cmd.__init__(self, startup_script='.cmd2rc')


if __name__ == '__main__':
    app = AliasAndStartup()
    app.cmdloop()
