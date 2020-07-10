#
# coding=utf-8

import pytest

import cmd2_ext_test
from cmd2 import CommandResult, cmd2

######
#
# define a class which implements a simple cmd2 application
#
######

OUT_MSG = 'this is the something command'


class ExampleApp(cmd2.Cmd):
    """An class to show how to use a plugin"""
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)

    def do_something(self, _):
        self.last_result = 5
        self.poutput(OUT_MSG)


# Define a tester class that brings in the external test mixin

class ExampleTester(cmd2_ext_test.ExternalTestMixin, ExampleApp):
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)

#
# You can't use a fixture to instantiate your app if you want to use
# to use the capsys fixture to capture the output. cmd2.Cmd sets
# internal variables to sys.stdout and sys.stderr on initialization
# and then uses those internal variables instead of sys.stdout. It does
# this so you can redirect output from within the app. The capsys fixture
# can't capture the output properly in this scenario.
#
# If you have extensive initialization needs, create a function
# to initialize your cmd2 application.


@pytest.fixture
def example_app():
    app = ExampleTester()
    app.fixture_setup()
    yield app
    app.fixture_teardown()


#####
#
# unit tests
#
#####

def test_something(example_app):
    # load our fixture
    # execute a command
    out = example_app.app_cmd("something")

    # validate the command output and result data
    assert isinstance(out, CommandResult)
    assert str(out.stdout).strip() == OUT_MSG
    assert out.data == 5
