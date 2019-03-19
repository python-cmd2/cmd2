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
    # noinspection PyUnresolvedReferences
    from contextlib2 import redirect_stdout, redirect_stderr
else:
    from contextlib import redirect_stdout, redirect_stderr


class CommandResult(namedtuple_with_defaults('CommandResult', ['stdout', 'stderr', 'data'])):
    """Encapsulates the results from a command.

    Named tuple attributes
    ----------------------
    stdout: str - Output captured from stdout while this command is executing
    stderr: str - Output captured from stderr while this command is executing. None if no error captured.
    data - Data returned by the command.

    Any combination of these fields can be used when developing a scripting API for a given command.
    By default stdout and stderr will be captured for you. If there is additional command specific data,
    then write that to cmd2's _last_result member. That becomes the data member of this tuple.

    In some cases, the data member may contain everything needed for a command and storing stdout
    and stderr might just be a duplication of data that wastes memory. In that case, the StdSim can
    be told not to store output with its pause_storage member. While this member is True, any output
    sent to StdSim won't be saved in its buffer.

    The code would look like this:
        if isinstance(self.stdout, StdSim):
            self.stdout.pause_storage = True

        if isinstance(sys.stderr, StdSim):
            sys.stderr.pause_storage = True

    See StdSim class in utils.py for more information

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

    def __call__(self, command: str, echo: Optional[bool] = None) -> CommandResult:
        """
        Provide functionality to call application commands by calling PyscriptBridge
        ex: app('help')
        :param command: command line being run
        :param echo: if True, output will be echoed to stdout/stderr while the command runs
                     this temporarily overrides the value of self.cmd_echo
        """
        if echo is None:
            echo = self.cmd_echo

        # This will be used to capture _cmd2_app.stdout and sys.stdout
        copy_cmd_stdout = StdSim(self._cmd2_app.stdout, echo)

        # This will be used to capture sys.stderr
        copy_stderr = StdSim(sys.stderr, echo)

        self._cmd2_app._last_result = None

        try:
            self._cmd2_app.stdout = copy_cmd_stdout
            with redirect_stdout(copy_cmd_stdout):
                with redirect_stderr(copy_stderr):
                    self._cmd2_app.onecmd_plus_hooks(command)
        finally:
            self._cmd2_app.stdout = copy_cmd_stdout.inner_stream

        # Save the output. If stderr is empty, set it to None.
        result = CommandResult(stdout=copy_cmd_stdout.getvalue(),
                               stderr=copy_stderr.getvalue() if copy_stderr.getvalue() else None,
                               data=self._cmd2_app._last_result)
        return result
