#!/usr/bin/env python
"""A simple example demonstrating the following how to emit a non-zero exit code in your cmd2 application."""

import cmd2


class ReplWithExitCode(cmd2.Cmd):
    """Example cmd2 application where we can specify an exit code when existing."""

    def __init__(self) -> None:
        super().__init__()

    @cmd2.with_argument_list
    def do_exit(self, arg_list: list[str]) -> bool:
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
                self.perror(f"{arg_list[0]} isn't a valid integer exit code")
                self.exit_code = 1

        return True


if __name__ == '__main__':
    import sys

    app = ReplWithExitCode()
    sys_exit_code = app.cmdloop()
    app.poutput(f'{sys.argv[0]!r} exiting with code: {sys_exit_code}')
    sys.exit(sys_exit_code)
