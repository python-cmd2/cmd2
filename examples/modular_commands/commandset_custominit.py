"""A simple example demonstrating a loadable command set."""

from cmd2 import (
    Cmd,
    CommandSet,
    Statement,
)


class CustomInitCommandSet(CommandSet[Cmd]):
    DEFAULT_CATEGORY = "Custom Init"

    def __init__(self, arg1, arg2) -> None:
        super().__init__()

        self._arg1 = arg1
        self._arg2 = arg2

    def do_show_arg1(self, _: Statement) -> None:
        """Show Arg 1."""
        self._cmd.poutput("Arg1: " + self._arg1)

    def do_show_arg2(self, _: Statement) -> None:
        """Show Arg 2."""
        self._cmd.poutput("Arg2: " + self._arg2)
