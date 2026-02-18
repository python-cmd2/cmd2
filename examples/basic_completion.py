#!/usr/bin/env python
"""A simple example demonstrating how to enable tab completion by assigning a completer function to do_* commands.

This also demonstrates capabilities of the following completer features included with cmd2:
- CompletionError exceptions
- delimiter_complete()

The recommended approach for tab completing is to use argparse-based completion.
For an example integrating tab completion with argparse, see argparse_completion.py.
"""

import functools
from typing import NoReturn

import cmd2

# This data is used to demonstrate delimiter_complete
file_strs = [
    '/home/user/file.db',
    '/home/user/file space.db',
    '/home/user/another.db',
    '/home/other user/maps.db',
    '/home/other user/tests.db',
]


class BasicCompletion(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__(auto_suggest=False, include_py=True)

    def do_delimiter_complete(self, statement: cmd2.Statement) -> None:
        """Tab completes files from a list using delimiter_complete."""
        self.poutput(f"Args: {statement.args}")

    # Use a partialmethod to set arguments to delimiter_complete
    complete_delimiter_complete = functools.partialmethod(cmd2.Cmd.delimiter_complete, match_against=file_strs, delimiter='/')

    def do_raise_error(self, statement: cmd2.Statement) -> None:
        """Demonstrates effect of raising CompletionError."""
        self.poutput(f"Args: {statement.args}")

    def complete_raise_error(self, _text: str, _line: str, _begidx: int, _endidx: int) -> NoReturn:
        """CompletionErrors can be raised if an error occurs while tab completing.

        Example use cases
            - Reading a database to retrieve a tab completion data set failed
            - A previous command line argument that determines the data set being completed is invalid
        """
        raise cmd2.CompletionError("This is how a CompletionError behaves")


if __name__ == '__main__':
    import sys

    app = BasicCompletion()
    sys.exit(app.cmdloop())
