# coding=utf-8
"""
A simple example demonstrating a loadable command set
"""
from cmd2 import Cmd, Statement, with_category
from cmd2_modular_cmds import CommandSet, register_command, with_default_category


@register_command
@with_category("AAA")
def do_another_command(cmd: Cmd, statement: Statement):
    """
    This is an example of registering an unbound function
    :param cmd:
    :param statement:
    :return:
    """
    cmd.poutput('Another Unbound Command: {}'.format(statement.args))


@with_default_category('Custom Init')
class CustomInitCommandSet(CommandSet):
    def __init__(self, arg1, arg2):
        super().__init__()

        self._arg1 = arg1
        self._arg2 = arg2

    def do_show_arg1(self, cmd: Cmd, _: Statement):
        cmd.poutput('Arg1: ' + self._arg1)

    def do_show_arg2(self, cmd: Cmd, _: Statement):
        cmd.poutput('Arg2: ' + self._arg2)
