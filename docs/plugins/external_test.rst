External Test Plugin
====================

Overview
~~~~~~~~

.. _cmd2_external_test_plugin:
   https://github.com/python-cmd2/cmd2/tree/cmdset_settables/plugins/ext_test

The `External Test Plugin <cmd2_external_test_plugin_>`_ supports testing of a cmd2 application by exposing access cmd2
commands with the same context as from within a cmd2 :ref:`Python Scripts <scripting-python-scripts>`.  This interface
captures ``stdout``, ``stderr``, as well as any application-specific data returned by the command.  This also allows
for verification of an application's support for :ref:`Python Scripts <scripting-python-scripts>` and enables the cmd2
application to be tested as part of a larger system integration test.


Example cmd2 Application
~~~~~~~~~~~~~~~~~~~~~~~~

The following short example shows how to mix in the external test plugin to create a fixture for testing
your cmd2 application.

Define your cmd2 application

.. code-block:: python

    import cmd2
    class ExampleApp(cmd2.Cmd):
        """An class to show how to use a plugin"""
        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, **kwargs)

        def do_something(self, arg):
            self.last_result = 5
            self.poutput('this is the something command')

Defining the test fixture
~~~~~~~~~~~~~~~~~~~~~~~~~

In your test, define a fixture for your cmd2 application

.. code-block:: python

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


Writing Tests
~~~~~~~~~~~~~

Now write your tests that validate your application using the :meth:`~cmd2_ext_test.ExternalTestMixin.app_cmd()`
function to access the cmd2 application's commands. This allows invocation of the application's commands in the
same format as a user would type. The results from calling a command matches what is returned
from running an python script with cmd2's :ref:`feature-builtin-commands-run-pyscript` command, which provides
``stdout``, ``stderr``, and the command's result data.

.. code-block:: python

    from cmd2 import CommandResult

    def test_something(example_app):
        # execute a command
        out = example_app.app_cmd("something")

        # validate the command output and result data
        assert isinstance(out, CommandResult)
        assert str(out.stdout).strip() == 'this is the something command'
        assert out.data == 5

