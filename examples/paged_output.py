#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the using paged output via the ppaged() method.
"""
import functools

import cmd2
from cmd2 import with_argument_list


class PagedOutput(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        cmd2.Cmd.__init__(self)

    @with_argument_list
    def do_page_file(self, args):
        """Read in a text file and display its output in a pager."""
        with open(args[0], 'r') as f:
            text = f.read()
        self.ppaged(text)

    complete_page_file = functools.partial(cmd2.path_complete)


if __name__ == '__main__':
    app = PagedOutput()
    app.cmdloop()
