"""Bridges calls made inside of a Python environment to the Cmd2 host app.

Maintains a reasonable degree of isolation between the two.
"""

import sys
from contextlib import redirect_stderr
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    NamedTuple,
    Optional,
    TextIO,
    Union,
    cast,
)

from .utils import (  # namedtuple_with_defaults,
    StdSim,
)

if TYPE_CHECKING:  # pragma: no cover
    import cmd2


class CommandResult(NamedTuple):
    """Encapsulates the results from a cmd2 app command.

    :stdout: str - output captured from stdout while this command is executing
    :stderr: str - output captured from stderr while this command is executing
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

    See [cmd2.utils.StdSim][] for more information.

    .. note::

       Named tuples are immutable. The contents are there for access,
       not for modification.
    """

    stdout: str = ''
    stderr: str = ''
    stop: bool = False
    data: Any = None

    def __bool__(self) -> bool:
        """Return True if the command succeeded, otherwise False."""
        # If data was set, then use it to determine success
        if self.data is not None:
            return bool(self.data)

        # Otherwise check if stderr was filled out
        return not self.stderr


class PyBridge:
    """Provides a Python API wrapper for application commands.

    :param cmd2_app: app being controlled by this PyBridge.
    :param add_to_history: If True, then add all commands run by this PyBridge to history.
                           Defaults to True.
    """

    def __init__(self, cmd2_app: 'cmd2.Cmd', *, add_to_history: bool = True) -> None:
        """Initialize PyBridge instances."""
        self._cmd2_app = cmd2_app
        self._add_to_history = add_to_history
        self.cmd_echo = False

        # Tells if any of the commands run via __call__ returned True for stop
        self.stop = False

    def __dir__(self) -> list[str]:
        """Return a custom set of attribute names."""
        attributes: list[str] = []
        attributes.insert(0, 'cmd_echo')
        return attributes

    def __call__(self, command: str, *, echo: Optional[bool] = None) -> CommandResult:
        """Provide functionality to call application commands by calling PyBridge.

        ex: app('help')
        :param command: command line being run
        :param echo: If provided, this temporarily overrides the value of self.cmd_echo while the
                     command runs. If True, output will be echoed to stdout/stderr. (Defaults to None)

        """
        if echo is None:
            echo = self.cmd_echo

        # Only capture sys.stdout if it's the same stream as self.stdout
        stdouts_match = self._cmd2_app.stdout == sys.stdout

        # This will be used to capture _cmd2_app.stdout and sys.stdout
        copy_cmd_stdout = StdSim(cast(Union[TextIO, StdSim], self._cmd2_app.stdout), echo=echo)

        # Pause the storing of stdout until onecmd_plus_hooks enables it
        copy_cmd_stdout.pause_storage = True

        # This will be used to capture sys.stderr
        copy_stderr = StdSim(sys.stderr, echo=echo)

        self._cmd2_app.last_result = None

        stop = False
        try:
            with self._cmd2_app.sigint_protection:
                self._cmd2_app.stdout = cast(TextIO, copy_cmd_stdout)
                if stdouts_match:
                    sys.stdout = self._cmd2_app.stdout

            with redirect_stderr(cast(IO[str], copy_stderr)):
                stop = self._cmd2_app.onecmd_plus_hooks(
                    command,
                    add_to_history=self._add_to_history,
                    py_bridge_call=True,
                )
        finally:
            with self._cmd2_app.sigint_protection:
                self._cmd2_app.stdout = cast(IO[str], copy_cmd_stdout.inner_stream)
                if stdouts_match:
                    sys.stdout = self._cmd2_app.stdout

                self.stop = stop or self.stop

        # Save the result
        return CommandResult(
            stdout=copy_cmd_stdout.getvalue(),
            stderr=copy_stderr.getvalue(),
            stop=stop,
            data=self._cmd2_app.last_result,
        )
