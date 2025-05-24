#!/usr/bin/env python
"""A simple example demonstrating the using paged output via the ppaged() method."""

import os

import cmd2


class PagedOutput(cmd2.Cmd):
    """Example cmd2 application which shows how to display output using a pager."""

    def __init__(self) -> None:
        super().__init__()

    def page_file(self, file_path: str, chop: bool = False) -> None:
        """Helper method to prevent having too much duplicated code."""
        filename = os.path.expanduser(file_path)
        try:
            with open(filename) as f:
                text = f.read()
            self.ppaged(text, chop=chop)
        except OSError as ex:
            self.pexcept(f'Error reading {filename!r}: {ex}')

    @cmd2.with_argument_list
    def do_page_wrap(self, args: list[str]) -> None:
        """Read in a text file and display its output in a pager, wrapping long lines if they don't fit.

        Usage: page_wrap <file_path>
        """
        if not args:
            self.perror('page_wrap requires a path to a file as an argument')
            return
        self.page_file(args[0], chop=False)

    complete_page_wrap = cmd2.Cmd.path_complete

    @cmd2.with_argument_list
    def do_page_truncate(self, args: list[str]) -> None:
        """Read in a text file and display its output in a pager, truncating long lines if they don't fit.

        Truncated lines can still be accessed by scrolling to the right using the arrow keys.

        Usage: page_chop <file_path>
        """
        if not args:
            self.perror('page_truncate requires a path to a file as an argument')
            return
        self.page_file(args[0], chop=True)

    complete_page_truncate = cmd2.Cmd.path_complete


if __name__ == '__main__':
    import sys

    app = PagedOutput()
    sys.exit(app.cmdloop())
