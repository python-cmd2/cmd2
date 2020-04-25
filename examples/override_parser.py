#!/usr/bin/env python
# coding=utf-8
# flake8: noqa F402
"""
The standard parser used by cmd2 built-in commands is Cmd2ArgumentParser.
The following code shows how to override it with your own parser class.
"""

# First set a value called argparse.cmd2_parser_module with the module that defines the custom parser
# See the code for custom_parser.py. It simply defines a parser and calls cmd2.set_default_argument_parser()
# with the custom parser's type.
import argparse

# Next import stuff from cmd2. It will import your module just before the cmd2.Cmd class file is imported
# and therefore override the parser class it uses on its commands.
from cmd2 import cmd2

argparse.cmd2_parser_module = 'examples.custom_parser'


if __name__ == '__main__':
    import sys
    app = cmd2.Cmd(use_ipython=True, persistent_history_file='cmd2_history.dat')
    app.self_in_py = True     # Enable access to "self" within the py command
    app.debug = True            # Show traceback if/when an exception occurs
    sys.exit(app.cmdloop())
