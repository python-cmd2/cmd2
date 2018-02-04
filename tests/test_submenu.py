# coding=utf-8
"""
Cmd2 testing for argument parsing
"""
import pytest

import cmd2
from conftest import run_cmd, StdOut


class SecondLevel(cmd2.Cmd):
    """To be used as a second level command class. """
    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = '2ndLevel '
        self.top_level_attr = None

    def do_say(self, line):
        self.stdout.write("You called a command in SecondLevel with '%s'. " % line)

    def help_say(self):
        self.stdout.write("This is a second level menu. Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]

    def do_get_top_level_attr(self, line):
        self.stdout.write(str(self.top_level_attr))

    def do_get_prompt(self, line):
        self.stdout.write(self.prompt)


second_level_cmd = SecondLevel()


@cmd2.AddSubmenu(second_level_cmd,
                 command='second',
                 aliases=('second_alias',),
                 shared_attributes=dict(top_level_attr='top_level_attr'))
class SubmenuApp(cmd2.Cmd):
    """To be used as the main / top level command class that will contain other submenus."""

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = 'TopLevel '
        self.top_level_attr = 123456789

    def do_say(self, line):
        self.stdout.write("You called a command in TopLevel with '%s'. " % line)

    def help_say(self):
        self.stdout.write("This is a top level submenu. Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]


@pytest.fixture
def submenu_app():
    app = SubmenuApp()
    second_level_cmd.stdout = app.stdout = StdOut()
    return app


def test_second_say_from_top_level(submenu_app):
    line = 'testing'
    out = run_cmd(submenu_app, 'second say ' + line)
    assert out == ["You called a command in SecondLevel with '%s'." % line]


def test_say_from_second_level():
    line = 'testing'
    out = run_cmd(second_level_cmd, 'say ' + line)
    assert out == ["You called a command in SecondLevel with '%s'." % line]


def test_help_second_say_from_top_level(submenu_app):
    out = run_cmd(submenu_app, 'help second say')
    assert out == ["This is a second level menu. Options are qwe, asd, zxc"]


def test_help_say_from_second_level():
    out = run_cmd(second_level_cmd, 'help say')
    assert out == ["This is a second level menu. Options are qwe, asd, zxc"]


def test_help_second(submenu_app):
    out = run_cmd(submenu_app, 'help second')
    out2 = run_cmd(second_level_cmd, 'help')
    assert out == out2


def test_from_top_help_second_say(submenu_app):
    out = run_cmd(submenu_app, 'help second say')
    out2 = run_cmd(second_level_cmd, 'help say')
    assert out == out2


def test_shared_attribute(submenu_app):
    out = run_cmd(submenu_app, 'second get_top_level_attr')
    assert out == [str(submenu_app.top_level_attr)]


if __name__ == '__main__':

    pytest.main('test_submenu.py -v')