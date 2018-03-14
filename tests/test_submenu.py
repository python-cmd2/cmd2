# coding=utf-8
"""
Cmd2 testing for argument parsing
"""
import pytest

import cmd2
from conftest import run_cmd, StdOut, normalize


class SecondLevelB(cmd2.Cmd):
    """To be used as a second level command class. """

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = '2ndLevel B '

    def do_get_top_level_attr(self, line):
        self.poutput(str(self.top_level_attr))

    def do_set_top_level_attr(self, line):
        self.top_level_attr = 987654321


class SecondLevel(cmd2.Cmd):
    """To be used as a second level command class. """

    def __init__(self, *args, **kwargs):
        cmd2.Cmd.__init__(self, *args, **kwargs)
        self.prompt = '2ndLevel '
        self.top_level_attr = None

    def do_say(self, line):
        self.poutput("You called a command in SecondLevel with '%s'. " % line)

    def help_say(self):
        self.poutput("This is a second level menu. Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]

    def do_get_top_level_attr(self, line):
        self.poutput(str(self.top_level_attr))

    def do_get_prompt(self, line):
        self.poutput(self.prompt)


second_level_cmd = SecondLevel()
second_level_b_cmd = SecondLevelB()


@cmd2.AddSubmenu(SecondLevelB(),
                 command='should_work_with_default_kwargs')
@cmd2.AddSubmenu(second_level_b_cmd,
                 command='secondb',
                 shared_attributes=dict(top_level_attr='top_level_attr'),
                 require_predefined_shares=False,
                 preserve_shares=True
                 )
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
        self.poutput("You called a command in TopLevel with '%s'. " % line)

    def help_say(self):
        self.poutput("This is a top level submenu. Options are qwe, asd, zxc")

    def complete_say(self, text, line, begidx, endidx):
        return [s for s in ['qwe', 'asd', 'zxc'] if s.startswith(text)]


@pytest.fixture
def submenu_app():
    app = SubmenuApp()
    app.stdout = StdOut()
    second_level_cmd.stdout = StdOut()
    second_level_b_cmd.stdout = StdOut()
    return app


@pytest.fixture
def secondlevel_app():
    app = SecondLevel()
    app.stdout = StdOut()
    return app


@pytest.fixture
def secondlevel_app_b():
    app = SecondLevelB()
    app.stdout = StdOut()
    return app


def run_submenu_cmd(app, second_level_app, cmd):
    """ Clear StdOut buffers, run the command, extract the buffer contents."""
    app.stdout.clear()
    second_level_app.stdout.clear()
    app.onecmd_plus_hooks(cmd)
    out1 = app.stdout.buffer
    out2 = second_level_app.stdout.buffer
    app.stdout.clear()
    second_level_app.stdout.clear()
    return normalize(out1), normalize(out2)


def test_submenu_say_from_top_level(submenu_app):
    line = 'testing'
    out1, out2 = run_submenu_cmd(submenu_app, second_level_cmd, 'say ' + line)
    assert len(out1) == 1
    assert len(out2) == 0
    assert out1[0] == "You called a command in TopLevel with {!r}.".format(line)


def test_submenu_second_say_from_top_level(submenu_app):
    line = 'testing'
    out1, out2 = run_submenu_cmd(submenu_app, second_level_cmd, 'second say ' + line)

    # No output expected from the top level
    assert out1 == []

    # Output expected from the second level
    assert len(out2) == 1
    assert out2[0] == "You called a command in SecondLevel with {!r}.".format(line)


def test_submenu_say_from_second_level(secondlevel_app):
    line = 'testing'
    out = run_cmd(secondlevel_app, 'say ' + line)
    assert out == ["You called a command in SecondLevel with '%s'." % line]


def test_submenu_help_second_say_from_top_level(submenu_app):
    out1, out2 = run_submenu_cmd(submenu_app, second_level_cmd, 'help second say')
    # No output expected from the top level
    assert out1 == []

    # Output expected from the second level
    assert out2 == ["This is a second level menu. Options are qwe, asd, zxc"]


def test_submenu_help_say_from_second_level(secondlevel_app):
    out = run_cmd(secondlevel_app, 'help say')
    assert out == ["This is a second level menu. Options are qwe, asd, zxc"]


def test_submenu_help_second(submenu_app):
    out1, out2 = run_submenu_cmd(submenu_app, second_level_cmd, 'help second')
    out3 = run_cmd(second_level_cmd, 'help')
    assert out2 == out3


def test_submenu_from_top_help_second_say(submenu_app):
    out1, out2 = run_submenu_cmd(submenu_app, second_level_cmd, 'help second say')
    out3 = run_cmd(second_level_cmd, 'help say')
    assert out2 == out3


def test_submenu_shared_attribute(submenu_app):
    out1, out2 = run_submenu_cmd(submenu_app, second_level_cmd, 'second get_top_level_attr')
    assert out2 == [str(submenu_app.top_level_attr)]


def test_submenu_shared_attribute_preserve(submenu_app):
    out1, out2 = run_submenu_cmd(submenu_app, second_level_b_cmd, 'secondb get_top_level_attr')
    assert out2 == [str(submenu_app.top_level_attr)]
    out1, out2 = run_submenu_cmd(submenu_app, second_level_b_cmd, 'secondb set_top_level_attr')
    assert submenu_app.top_level_attr == 987654321
    out1, out2 = run_submenu_cmd(submenu_app, second_level_b_cmd, 'secondb get_top_level_attr')
    assert out2 == [str(987654321)]
