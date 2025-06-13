# External Test Plugin

## Overview

The [External Test Plugin](https://github.com/python-cmd2/cmd2/tree/master/plugins/ext_test)
supports testing of a cmd2 application by exposing access to cmd2 commands with the same context as
from within a cmd2 [Python Script](../features/scripting.md#python-scripts). This interface captures
`stdout`, `stderr`, as well as any application-specific data returned by the command. This also
allows for verification of an application's support for
[Python Scripts](../features/scripting.md#python-scripts) and enables the cmd2 application to be
tested as part of a larger system integration test.

## Example cmd2 Application

The following short example shows how to mix in the external test plugin to create a fixture for
testing your cmd2 application.

Define your cmd2 application

```py
import cmd2
class ExampleApp(cmd2.Cmd):
    """An class to show how to use a plugin"""
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)

    def do_something(self, arg):
        self.last_result = 5
        self.poutput('this is the something command')
```

## Defining the test fixture

In your test, define a fixture for your cmd2 application

```py
import cmd2_ext_test
import pytest

class ExampleAppTester(cmd2_ext_test.ExternalTestMixin, ExampleApp):
    def __init__(self, *args, **kwargs):
        # gotta have this or neither the plugin or cmd2 will initialize
        super().__init__(*args, **kwargs)

@pytest.fixture
def example_app():
    app = ExampleAppTester()
    app.fixture_setup()
    yield app
    app.fixture_teardown()
```

## Writing Tests

Now write your tests that validate your application using the
`cmd2_ext_test.ExternalTestMixin.app_cmd` function to access the cmd2 application's commands. This
allows invocation of the application's commands in the same format as a user would type. The results
from calling a command matches what is returned from running an python script with cmd2's
[run_pyscript](../features/builtin_commands.md#run_pyscript) command, which provides `stdout`,
`stderr`, and the command's result data.

```py
from cmd2 import CommandResult

def test_something(example_app):
    # execute a command
    out = example_app.app_cmd("something")

    # validate the command output and result data
    assert isinstance(out, CommandResult)
    assert str(out.stdout).strip() == 'this is the something command'
    assert out.data == 5
```
