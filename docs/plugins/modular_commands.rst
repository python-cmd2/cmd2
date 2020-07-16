Modular Commands Plugin
=======================

Overview
--------

.. _cmd2_modular_commands_plugin:
   https://github.com/python-cmd2/cmd2/tree/master/plugins/modular_commands/

The cmd2_modular_commands_plugin_ enables developers to modularize their command definitions into Command Sets. Command sets represent
a logical grouping of commands within an cmd2 application. By default, all CommandSets will be discovered and loaded
automatically when the cmd2.Cmd class is instantiated with this mixin. This also enables the developer to
dynamically add/remove commands from the cmd2 application. This could be useful for loadable plugins that
add additional capabilities.

Features
~~~~~~~~

* Arbitrary Functions as Commands - Functions can be registered as commands in cmd2.
* Modular Command Sets - Commands can be broken into separate modules rather than in one god class holding all commands.
* Automatic Command Discovery - In your application, merely defining and importing a CommandSet is sufficient for
  cmd2 to discover and load your command. No manual registration is necessary.
* Dynamically Loadable Commands - Command functions and CommandSets can both be loaded and unloaded dynamically
  during application execution. This can enable features such as dynamically
  loaded modules that add additional commands.

See the examples for more details: https://github.com/python-cmd2/cmd2/tree/master/plugins/command_sets/examples


Defining Commands
-----------------

Class Definition
~~~~~~~~~~~~~~~~

The following short example shows how to add the ModularCommandsMixin to your cmd2 application.

Define your cmd2 application

.. code-block:: python

    import cmd2
    from cmd2_modular_cmds import ModularCommandsMixin

    class ExampleApp(ModularCommandsMixin, cmd2.Cmd):
        """An class to show how to use a plugin"""
        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, **kwargs)

        def do_something(self, arg):
            self.last_result = 5
            self.poutput('this is the something command')

Command Functions
~~~~~~~~~~~~~~~~~

Individual functions can be registered as commands with khe ``register_command`` decorator. It can be used with
other cmd2 decorators without problems. The order of decoration also does not matter.

Any functions defined with your command function that match ``help_`` or ``complete_`` are also detected
and registered as help and completion functions for the command.

.. code-block:: python

    import cmd2
    from cmd2_modular_cmds import ModularCommandsMixin, register_command

    @register_command
    @cmd2.with_category("AAA")
    def do_function_as_command(cmd: cmd2.Cmd, statement: cmd2.Statement):
        """
        This is an example of registering a function as a command
        :param cmd:
        :param statement:
        :return:
        """
        cmd.poutput('Unbound Command: {}'.format(statement.args))

    # This is detected and registered as the help function for `function_as_command`
    def help_function_as_command(cmd: cmd2.Cmd):
        cmd.poutput('Help for func_with_help')


    class ExampleApp(ModularCommandsMixin, cmd2.Cmd):
        """An class to show how to use a plugin"""
        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, **kwargs)

        def do_something(self, arg):
            self.last_result = 5
            self.poutput('this is the something command')


Command Sets
~~~~~~~~~~~~~

CommandSets group multiple commands together. The plugin will inspect functions within a ``CommandSet``
using the same rules as when they're defined in ``cmd2.Cmd``. Commands must be prefixed with ``do_``, help
functions with ``help_``, and completer functions with ``complete_``.

A new decorator ``with_default_category`` is provided to categorize all commands within a CommandSet in the
same command category.  Individual commands in a CommandSet may be override the default category by specifying a
specific category with ``cmd.with_category``.

CommandSet methods will always expect self, and cmd2.Cmd as the first two parameters.

.. code-block:: python

    import cmd2
    from cmd2_modular_cmds import ModularCommandsMixin, CommandSet, with_default_category

    @with_default_category('My Category')
    class CustomInitCommandSet(CommandSet):
        def __init__(self, arg1, arg2):
            super().__init__()

            self._arg1 = arg1
            self._arg2 = arg2

        def do_show_arg1(self, cmd: cmd2.Cmd, _: cmd2.Statement):
            cmd.poutput('Arg1: ' + self._arg1)

        def do_show_arg2(self, cmd: cmd2.Cmd, _: cmd2.Statement):
            cmd.poutput('Arg2: ' + self._arg2)

    class ExampleApp(ModularCommandsMixin, cmd2.Cmd):
        """
        An class to show how to use a plugin.
        CommandSets are automatically loaded. Nothing needs to be done.
        """
        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, **kwargs)

        def do_something(self, arg):
            self.last_result = 5
            self.poutput('this is the something command')


