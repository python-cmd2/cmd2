# coding=utf-8
"""
Bridges calls made inside of a Python environment to the Cmd2 host app
while maintaining a reasonable degree of isolation between the two.
"""

import sys
from contextlib import redirect_stderr, redirect_stdout
from typing import Optional

from .utils import StdSim, namedtuple_with_defaults


class CommandResult(namedtuple_with_defaults('CommandResult', ['stdout', 'stderr', 'stop', 'data'])):
    """Encapsulates the results from a cmd2 app command

    :stdout: str - output captured from stdout while this command is executing
    :stderr: str - output captured from stderr while this command is executing
             None if no error captured.
    :stop: bool - return value of onecmd_plus_hooks after it runs the given
           command line.
    :data: possible data populated by the command.

    Any combination of these fields can be used when developing a scripting API
    for a given command. By default stdout, stderr, and stop will be captured
    for you. If there is additional command specific data, then write that to
    cmd2's last_result member. That becomes the data member of this tuple.

    In some cases, the data member may contain everything needed for a command
    and storing stdout and stderr might just be a duplication of data that
    wastes memory. In that case, the StdSim can be told not to store output
    with its pause_storage member. While this member is True, any output sent
    to StdSim won't be saved in its buffer.

    The code would look like this::

        if isinstance(self.stdout, StdSim):
            self.stdout.pause_storage = True

        if isinstance(sys.stderr, StdSim):
            sys.stderr.pause_storage = True

    See :class:`~cmd2.utils.StdSim` for more information.

    .. note::

       Named tuples are immutable. The contents are there for access,
       not for modification.
    """
    def __bool__(self) -> bool:
        """Returns True if the command succeeded, otherwise False"""

        # If data has a __bool__ method, then call it to determine success of command
        if self.data is not None and callable(getattr(self.data, '__bool__', None)):
            return bool(self.data)

        # Otherwise check if stderr was filled out
        else:
            return not self.stderr


class PyBridge:
    """Provides a Python API wrapper for application commands."""
    def __init__(self, cmd2_app):
        self._cmd2_app = cmd2_app
        self.cmd_echo = False

        # Tells if any of the commands run via __call__ returned True for stop
        self.stop = False

    def __dir__(self):
        """Return a custom set of attribute names"""
        attributes = []
        attributes.insert(0, 'cmd_echo')
        return attributes

    def __call__(self, command: str, *, echo: Optional[bool] = None) -> CommandResult:
        """
        Provide functionality to call application commands by calling PyBridge
        ex: app('help')
        :param command: command line being run
        :param echo: If provided, this temporarily overrides the value of self.cmd_echo while the
                     command runs. If True, output will be echoed to stdout/stderr. (Defaults to None)

        """
        if echo is None:
            echo = self.cmd_echo

        # This will be used to capture _cmd2_app.stdout and sys.stdout
        copy_cmd_stdout = StdSim(self._cmd2_app.stdout, echo=echo)

        # Pause the storing of stdout until onecmd_plus_hooks enables it
        copy_cmd_stdout.pause_storage = True

        # This will be used to capture sys.stderr
        copy_stderr = StdSim(sys.stderr, echo=echo)

        self._cmd2_app.last_result = None

        stop = False
        try:
            self._cmd2_app.stdout = copy_cmd_stdout
            with redirect_stdout(copy_cmd_stdout):
                with redirect_stderr(copy_stderr):
                    stop = self._cmd2_app.onecmd_plus_hooks(command, py_bridge_call=True)
        finally:
            with self._cmd2_app.sigint_protection:
                self._cmd2_app.stdout = copy_cmd_stdout.inner_stream
                self.stop = stop or self.stop

        # Save the output. If stderr is empty, set it to None.
        result = CommandResult(stdout=copy_cmd_stdout.getvalue(),
                               stderr=copy_stderr.getvalue() if copy_stderr.getvalue() else None,
                               stop=stop,
                               data=self._cmd2_app.last_result)
        return result
