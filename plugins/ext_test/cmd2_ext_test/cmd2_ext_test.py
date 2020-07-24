#
# coding=utf-8
"""External test interface plugin"""

from typing import TYPE_CHECKING, Optional

import cmd2

if TYPE_CHECKING:  # pragma: no cover
    _Base = cmd2.Cmd
else:
    _Base = object


class ExternalTestMixin(_Base):
    """A cmd2 plugin (mixin class) that exposes an interface to execute application commands from python"""

    def __init__(self, *args, **kwargs):
        """

        :type self: cmd2.Cmd
        :param args:
        :param kwargs:
        """
        # code placed here runs before cmd2 initializes
        super().__init__(*args, **kwargs)
        assert isinstance(self, cmd2.Cmd)
        # code placed here runs after cmd2 initializes
        self._pybridge = cmd2.py_bridge.PyBridge(self)

    def app_cmd(self, command: str, echo: Optional[bool] = None) -> cmd2.CommandResult:
        """
        Run the application command

        :param command: The application command as it would be written on the cmd2 application prompt
        :param echo: Flag whether the command's output should be echoed to stdout/stderr
        :return: A CommandResult object that captures stdout, stderr, and the command's result object
        """
        assert isinstance(self, cmd2.Cmd) and isinstance(self, ExternalTestMixin)
        try:
            self._in_py = True

            return self._pybridge(command, echo=echo)

        finally:
            self._in_py = False

    def fixture_setup(self):
        """
        Replicates the behavior of `cmdloop()` preparing the state of the application
        :type self: cmd2.Cmd
        """

        for func in self._preloop_hooks:
            func()
        self.preloop()

    def fixture_teardown(self):
        """
        Replicates the behavior of `cmdloop()` tearing down the application

        :type self: cmd2.Cmd
        """
        # assert isinstance(self, cmd2.Cmd) and isinstance(self, ExternalTestMixin)
        for func in self._postloop_hooks:
            func()
        self.postloop()
