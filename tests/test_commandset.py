# coding=utf-8
# flake8: noqa E302
"""
Test CommandSet
"""

from typing import List
import pytest

import cmd2
from cmd2 import utils


# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock


@cmd2.register_command
@cmd2.with_category("AAA")
def do_unbound(cmd: cmd2.Cmd, statement: cmd2.Statement):
    """
    This is an example of registering an unbound function

    :param cmd:
    :param statement:
    :return:
    """
    cmd.poutput('Unbound Command: {}'.format(statement.args))


@cmd2.with_default_category('Command Set')
class TestCommandSet(cmd2.CommandSet):
    def do_apple(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Apple!')

    def do_banana(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Banana Command"""
        cmd.poutput('Banana!!')

    def do_cranberry(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Cranberry!!')

    def help_cranberry(self, cmd: cmd2.Cmd):
        cmd.stdout.write('This command does diddly squat...\n')

    def do_durian(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        """Durian Command"""
        cmd.poutput('Durian!!')

    def complete_durian(self, cmd: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        return utils.basic_complete(text, line, begidx, endidx, ['stinks', 'smells', 'disgusting'])

    @cmd2.with_category('Alone')
    def do_elderberry(self, cmd: cmd2.Cmd, statement: cmd2.Statement):
        cmd.poutput('Elderberry!!')


class WithCommandSets(cmd2.Cmd):
    """Class for testing custom help_* methods which override docstring help."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


@pytest.fixture
def command_sets_app():
    app = WithCommandSets()
    return app


def test_autoload_commands(command_sets_app):
    cmds_cats, cmds_doc, cmds_undoc, help_topics = command_sets_app._build_command_info()

    assert 'AAA' in cmds_cats
    assert 'unbound' in cmds_cats['AAA']

    assert 'Alone' in cmds_cats
    assert 'elderberry' in cmds_cats['Alone']

    assert 'Command Set' in cmds_cats
    assert 'cranberry' in cmds_cats['Command Set']



