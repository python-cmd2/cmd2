#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the using paged output via the ppaged() method.
"""

import cmd2


class PagedOutput(cmd2.Cmd):
    """ Example cmd2 application where we create commands that just print the arguments they are called with."""

    def __init__(self):
        super().__init__()

    @cmd2.with_argument_list
    def do_page_file(self, args):
        """Read in a text file and display its output in a pager."""
        if not args:
            self.perror('page_file requires a path to a file as an argument', traceback_war=False)
            return

        with open(args[0], 'r') as f:
            text = f.read()
        self.ppaged(text)

    complete_page_file = cmd2.Cmd.path_complete


if __name__ == '__main__':
    app = PagedOutput()
    app.cmdloop()
