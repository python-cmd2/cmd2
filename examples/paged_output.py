#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the using paged output via the ppaged() method.
"""
import os
from typing import List

import cmd2


class PagedOutput(cmd2.Cmd):
    """ Example cmd2 application which shows how to display output using a pager."""

    def __init__(self):
        super().__init__()

    @cmd2.with_argument_list
    def do_page_file(self, args: List[str]):
        """Read in a text file and display its output in a pager.

        Usage: page_file <file_path>
        """
        if not args:
            self.perror('page_file requires a path to a file as an argument', traceback_war=False)
            return

        filename = os.path.expanduser(args[0])
        try:
            with open(filename, 'r') as f:
                text = f.read()
            self.ppaged(text)
        except FileNotFoundError as ex:
            self.perror('ERROR: file {!r} not found'.format(filename), traceback_war=False)

    complete_page_file = cmd2.Cmd.path_complete


if __name__ == '__main__':
    app = PagedOutput()
    app.cmdloop()
