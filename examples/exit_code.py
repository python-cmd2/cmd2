#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following how to emit a non-zero exit code in your cmd2 application.
"""
from typing import List

import cmd2


class ReplWithExitCode(cmd2.Cmd):
    """ Example cmd2 application where we can specify an exit code when existing."""

    def __init__(self):
        super().__init__()

    @cmd2.with_argument_list
    def do_exit(self, arg_list: List[str]) -> bool:
        """Exit the application with an optional exit code.

Usage:  exit [exit_code]
    Where:
        * exit_code - integer exit code to return to the shell
"""
        # If an argument was provided
        if arg_list:
            try:
                self.exit_code = int(arg_list[0])
            except ValueError:
                self.perror("{} isn't a valid integer exit code".format(arg_list[0]))
                self.exit_code = -1

        return True


if __name__ == '__main__':
    import sys
    app = ReplWithExitCode()
    sys_exit_code = app.cmdloop()
    app.poutput('{!r} exiting with code: {}'.format(sys.argv[0], sys_exit_code))
    sys.exit(sys_exit_code)
