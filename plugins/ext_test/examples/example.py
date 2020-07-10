#
# coding=utf-8
# import cmd2
import cmd2
import cmd2.py_bridge
import cmd2_ext_test


class Example(cmd2.Cmd):
    """An class to show how to use a plugin"""
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)

    def do_something(self, arg):
        self.last_result = 5
        self.poutput('this is the something command')


class ExampleTester(cmd2_ext_test.ExternalTestMixin, Example):
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)


if __name__ == '__main__':
    app = ExampleTester()

    try:
        app.fixture_setup()

        out = app.app_cmd("something")
        assert isinstance(out, cmd2.CommandResult)

        assert out.data == 5

    finally:
        app.fixture_teardown()
