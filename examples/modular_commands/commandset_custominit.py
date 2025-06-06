"""A simple example demonstrating a loadable command set."""

from cmd2 import (
    Cmd,
    CommandSet,
    Statement,
    with_default_category,
)


@with_default_category('Custom Init')
class CustomInitCommandSet(CommandSet):
    def __init__(self, arg1, arg2) -> None:
        super().__init__()

        self._arg1 = arg1
        self._arg2 = arg2

    def do_show_arg1(self, _cmd: Cmd, _: Statement) -> None:
        self._cmd.poutput('Arg1: ' + self._arg1)

    def do_show_arg2(self, _cmd: Cmd, _: Statement) -> None:
        self._cmd.poutput('Arg2: ' + self._arg2)
