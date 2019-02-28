# coding=utf-8
"""
Bridges calls made inside of pyscript with the Cmd2 host app while maintaining a reasonable
degree of isolation between the two

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""

import sys
from typing import Optional

from .utils import namedtuple_with_defaults, StdSim

# Python 3.4 require contextlib2 for temporarily redirecting stderr and stdout
if sys.version_info < (3, 5):
    from contextlib2 import redirect_stdout, redirect_stderr
else:
    from contextlib import redirect_stdout, redirect_stderr


class CommandResult(namedtuple_with_defaults('CommandResult', ['stdout', 'stderr', 'data'])):
    """Encapsulates the results from a command.

    Named tuple attributes
    ----------------------
    stdout: str - Output captured from stdout while this command is executing
    stderr: str - Output captured from stderr while this command is executing. None if no error captured
    data - Data returned by the command.

    NOTE: Named tuples are immutable.  So the contents are there for access, not for modification.
    """
    def __bool__(self) -> bool:
        """Returns True if the command succeeded, otherwise False"""

        # If data has a __bool__ method, then call it to determine success of command
        if self.data is not None and callable(getattr(self.data, '__bool__', None)):
            return bool(self.data)

        # Otherwise check if stderr was filled out
        else:
            return not self.stderr


class PyscriptBridge(object):
    """Preserves the legacy 'cmd' interface for pyscript while also providing a new python API wrapper for
    application commands."""
    def __init__(self, cmd2_app):
        self._cmd2_app = cmd2_app
        self._last_result = None
        self.cmd_echo = False

    def __dir__(self):
        """Return a custom set of attribute names"""
        attributes = []
        attributes.insert(0, 'cmd_echo')
        return attributes

    def __call__(self, command: str, echo: Optional[bool]=None) -> CommandResult:
        """
        Provide functionality to call application commands by calling PyscriptBridge
        ex: app('help')
        :param command: command line being run
        :param echo: if True, output will be echoed to stdout/stderr while the command runs
                     this temporarily overrides the value of self.cmd_echo
        """
        if echo is None:
            echo = self.cmd_echo

        copy_stdout = StdSim(sys.stdout, echo)
        copy_stderr = StdSim(sys.stderr, echo)

        copy_cmd_stdout = StdSim(self._cmd2_app.stdout, echo)

        self._cmd2_app._last_result = None

        try:
            self._cmd2_app.stdout = copy_cmd_stdout
            with redirect_stdout(copy_stdout):
                with redirect_stderr(copy_stderr):
                    # Include a newline in case it's a multiline command
                    self._cmd2_app.onecmd_plus_hooks(command + '\n')
        finally:
            self._cmd2_app.stdout = copy_cmd_stdout.inner_stream

        # if stderr is empty, set it to None
        stderr = copy_stderr.getvalue() if copy_stderr.getvalue() else None

        outbuf = copy_cmd_stdout.getvalue() if copy_cmd_stdout.getvalue() else copy_stdout.getvalue()
        result = CommandResult(stdout=outbuf, stderr=stderr, data=self._cmd2_app._last_result)
        return result
