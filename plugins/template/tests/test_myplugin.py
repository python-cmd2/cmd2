#
# coding=utf-8

import cmd2_myplugin
from cmd2 import cmd2

######
#
# define a class which uses our plugin and some convenience functions
#
######


class MyApp(cmd2_myplugin.MyPluginMixin, cmd2.Cmd):
    """Simple subclass of cmd2.Cmd with our SayMixin plugin included."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @cmd2_myplugin.empty_decorator
    def do_empty(self, args):
        self.poutput("running the empty command")

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


def init_app():
    app = MyApp()
    return app


#####
#
# unit tests
#
#####

def test_say(capsys):
    # call our initialization function instead of using a fixture
    app = init_app()
    # run our mixed in command
    app.onecmd_plus_hooks('say hello')
    # use the capsys fixture to retrieve the output on stdout and stderr
    out, err = capsys.readouterr()
    # make our assertions
    assert out == 'in postparsing hook\nhello\n'
    assert not err


def test_decorator(capsys):
    # call our initialization function instead of using a fixture
    app = init_app()
    # run one command in the app
    app.onecmd_plus_hooks('empty')
    # use the capsys fixture to retrieve the output on stdout and stderr
    out, err = capsys.readouterr()
    # make our assertions
    assert out == 'in postparsing hook\nin the empty decorator\nrunning the empty command\n'
    assert not err
