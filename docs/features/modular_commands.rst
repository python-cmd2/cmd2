Modular Commands
================

Overview
--------

Cmd2 also enables developers to modularize their command definitions into ``CommandSet`` objects. CommandSets represent
a logical grouping of commands within an cmd2 application. By default, all CommandSets will be discovered and loaded
automatically when the cmd2.Cmd class is instantiated with this mixin. This also enables the developer to
dynamically add/remove commands from the cmd2 application. This could be useful for loadable plugins that
add additional capabilities. Additionally, it allows for object-oriented encapsulation and garbage collection of state
that is specific to a CommandSet.

Features
~~~~~~~~

* Modular Command Sets - Commands can be broken into separate modules rather than in one god class holding all
  commands.
* Automatic Command Discovery - In your application, merely defining and importing a CommandSet is sufficient for
  cmd2 to discover and load your command. No manual registration is necessary.
* Dynamically Loadable/Unloadable Commands - Command functions and CommandSets can both be loaded and unloaded
  dynamically during application execution. This can enable features such as dynamically loaded modules that
  add additional commands.
* Events handlers - Four event handlers are provided in ``CommandSet`` class for custom initialization
  and cleanup steps. See :ref:`features/modular_commands:Event Handlers`.
* Subcommand Injection - Subcommands can be defined separately from the base command. This allows for a more
  action-centric instead of object-centric command system while still organizing your code and handlers around the
  objects being managed.

See API documentation for :attr:`cmd2.command_definition.CommandSet`

See [the examples](https://github.com/python-cmd2/cmd2/tree/master/examples/modular_commands) for more details.


Defining Commands
-----------------

Command Sets
~~~~~~~~~~~~~

CommandSets group multiple commands together. The plugin will inspect functions within a ``CommandSet``
using the same rules as when they're defined in ``cmd2.Cmd``. Commands must be prefixed with ``do_``, help
functions with ``help_``, and completer functions with ``complete_``.

A new decorator ``with_default_category`` is provided to categorize all commands within a CommandSet in the
same command category.  Individual commands in a CommandSet may be override the default category by specifying a
specific category with ``cmd2.with_category``.

CommandSet command methods will always expect the same parameters as when defined in a ``cmd2.Cmd`` sub-class,
except that ``self`` will now refer to the ``CommandSet`` instead of the cmd2 instance. The cmd2 instance can
be accessed through ``self._cmd`` that is populated when the ``CommandSet`` is registered.

CommandSets will only be auto-loaded if the constructor takes no arguments.
If you need to provide constructor arguments, see :ref:`features/modular_commands:Manual CommandSet Construction`

.. code-block:: python

    import cmd2
    from cmd2 import CommandSet, with_default_category

    @with_default_category('My Category')
    class AutoLoadCommandSet(CommandSet):
        def __init__(self):
            super().__init__()

        def do_hello(self, _: cmd2.Statement):
            self._cmd.poutput('Hello')

        def do_world(self, _: cmd2.Statement):
            self._cmd.poutput('World')

    class ExampleApp(cmd2.Cmd):
        """
        CommandSets are automatically loaded. Nothing needs to be done.
        """
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def do_something(self, arg):
            self.poutput('this is the something command')


Manual CommandSet Construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a CommandSet class requires parameters to be provided to the constructor, you man manually construct
CommandSets and pass in the constructor to Cmd2.

.. code-block:: python

    import cmd2
    from cmd2 import CommandSet, with_default_category

    @with_default_category('My Category')
    class CustomInitCommandSet(CommandSet):
        def __init__(self, arg1, arg2):
            super().__init__()

            self._arg1 = arg1
            self._arg2 = arg2

        def do_show_arg1(self, _: cmd2.Statement):
            self._cmd.poutput('Arg1: ' + self._arg1)

        def do_show_arg2(self, _: cmd2.Statement):
            self._cmd.poutput('Arg2: ' + self._arg2)

    class ExampleApp(cmd2.Cmd):
        """
        CommandSets with constructor parameters are provided in the constructor
        """
        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, **kwargs)

        def do_something(self, arg):
            self.last_result = 5
            self.poutput('this is the something command')


    def main():
        my_commands = CustomInitCommandSet(1, 2)
        app = ExampleApp(command_sets=[my_commands])
        app.cmdloop()


Dynamic Commands
~~~~~~~~~~~~~~~~

You can also dynamically load and unload commands by installing and removing CommandSets at runtime. For example,
if you could support runtime loadable plugins or add/remove commands based on your state.

You may need to disable command auto-loading if you need dynamically load commands at runtime.

.. code-block:: python

    import argparse
    import cmd2
    from cmd2 import CommandSet, with_argparser, with_category, with_default_category


    @with_default_category('Fruits')
    class LoadableFruits(CommandSet):
        def __init__(self):
            super().__init__()

        def do_apple(self, _: cmd2.Statement):
            self._cmd.poutput('Apple')

        def do_banana(self, _: cmd2.Statement):
            self._cmd.poutput('Banana')


    @with_default_category('Vegetables')
    class LoadableVegetables(CommandSet):
        def __init__(self):
            super().__init__()

        def do_arugula(self, _: cmd2.Statement):
            self._cmd.poutput('Arugula')

        def do_bokchoy(self, _: cmd2.Statement):
            self._cmd.poutput('Bok Choy')


    class ExampleApp(cmd2.Cmd):
        """
        CommandSets are loaded via the `load` and `unload` commands
        """

        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, auto_load_commands=False, **kwargs)

            self._fruits = LoadableFruits()
            self._vegetables = LoadableVegetables()

        load_parser = cmd2.Cmd2ArgumentParser()
        load_parser.add_argument('cmds', choices=['fruits', 'vegetables'])

        @with_argparser(load_parser)
        @with_category('Command Loading')
        def do_load(self, ns: argparse.Namespace):
            if ns.cmds == 'fruits':
                try:
                    self.register_command_set(self._fruits)
                    self.poutput('Fruits loaded')
                except ValueError:
                    self.poutput('Fruits already loaded')

            if ns.cmds == 'vegetables':
                try:
                    self.register_command_set(self._vegetables)
                    self.poutput('Vegetables loaded')
                except ValueError:
                    self.poutput('Vegetables already loaded')

        @with_argparser(load_parser)
        def do_unload(self, ns: argparse.Namespace):
            if ns.cmds == 'fruits':
                self.unregister_command_set(self._fruits)
                self.poutput('Fruits unloaded')

            if ns.cmds == 'vegetables':
                self.unregister_command_set(self._vegetables)
                self.poutput('Vegetables unloaded')


    if __name__ == '__main__':
        app = ExampleApp()
        app.cmdloop()


Event Handlers
--------------
The following functions are called at different points in the ``CommandSet`` life cycle.

``on_register(self, cmd) -> None`` - Called by cmd2.Cmd as the first step to
registering a CommandSet. The commands defined in this class have not be
added to the CLI object at this point. Subclasses can override this to
perform any initialization requiring access to the Cmd object
(e.g. configure commands and their parsers based on CLI state data).

``on_registered(self) -> None`` - Called by cmd2.Cmd after a CommandSet is
registered and all its commands have been added to the CLI. Subclasses can
override this to perform custom steps related to the newly added commands
(e.g. setting them to a disabled state).

``on_unregister(self) -> None`` - Called by ``cmd2.Cmd`` as the first step to
unregistering a CommandSet. Subclasses can override this to perform any cleanup
steps which require their commands being registered in the CLI.

``on_unregistered(self) -> None`` - Called by ``cmd2.Cmd`` after a CommandSet
has been unregistered and all its commands removed from the CLI. Subclasses can
override this to perform remaining cleanup steps.


Injecting Subcommands
----------------------

Description
~~~~~~~~~~~
Using the `with_argparse` decorator, it is possible to define subcommands for your command. This has a tendency to
either drive your interface into an object-centric interface. For example, imagine you have a tool that manages your
media collection and you want to manage movies or shows. An object-centric approach would push you to have base
commands such as `movies` and `shows` which each have subcommands `add`, `edit`, `list`, `delete`. If you wanted to
present an action-centric command set, so that `add`, `edit`, `list`, and `delete` are the base commands, you'd have
to organize your code around these similar actions rather than organizing your code around similar objects being
managed.

Subcommand injection allows you to inject subcommands into a base command to present an interface that is sensible to
a user while still organizing your code in whatever structure make more logical sense to the developer.

Example
~~~~~~~

This example is a variation on the Dynamic Commands example above. A `cut` command is introduced as a base
command and each CommandSet

.. code-block:: python

    import argparse
    import cmd2
    from cmd2 import CommandSet, with_argparser, with_category, with_default_category


    @with_default_category('Fruits')
    class LoadableFruits(CommandSet):
        def __init__(self):
            super().__init__()

        def do_apple(self, _: cmd2.Statement):
            self._cmd.poutput('Apple')

        banana_parser = cmd2.Cmd2ArgumentParser()
        banana_parser.add_argument('direction', choices=['discs', 'lengthwise'])

        @cmd2.as_subcommand_to('cut', 'banana', banana_parser)
        def cut_banana(self, ns: argparse.Namespace):
            """Cut banana"""
            self._cmd.poutput('cutting banana: ' + ns.direction)


    @with_default_category('Vegetables')
    class LoadableVegetables(CommandSet):
        def __init__(self):
            super().__init__()

        def do_arugula(self, _: cmd2.Statement):
            self._cmd.poutput('Arugula')

        bokchoy_parser = cmd2.Cmd2ArgumentParser()
        bokchoy_parser.add_argument('style', choices=['quartered', 'diced'])

        @cmd2.as_subcommand_to('cut', 'bokchoy', bokchoy_parser)
        def cut_bokchoy(self, _: argparse.Namespace):
            self._cmd.poutput('Bok Choy')


    class ExampleApp(cmd2.Cmd):
        """
        CommandSets are automatically loaded. Nothing needs to be done.
        """

        def __init__(self, *args, **kwargs):
            # gotta have this or neither the plugin or cmd2 will initialize
            super().__init__(*args, auto_load_commands=False, **kwargs)

            self._fruits = LoadableFruits()
            self._vegetables = LoadableVegetables()

        load_parser = cmd2.Cmd2ArgumentParser()
        load_parser.add_argument('cmds', choices=['fruits', 'vegetables'])

        @with_argparser(load_parser)
        @with_category('Command Loading')
        def do_load(self, ns: argparse.Namespace):
            if ns.cmds == 'fruits':
                try:
                    self.register_command_set(self._fruits)
                    self.poutput('Fruits loaded')
                except ValueError:
                    self.poutput('Fruits already loaded')

            if ns.cmds == 'vegetables':
                try:
                    self.register_command_set(self._vegetables)
                    self.poutput('Vegetables loaded')
                except ValueError:
                    self.poutput('Vegetables already loaded')

        @with_argparser(load_parser)
        def do_unload(self, ns: argparse.Namespace):
            if ns.cmds == 'fruits':
                self.unregister_command_set(self._fruits)
                self.poutput('Fruits unloaded')

            if ns.cmds == 'vegetables':
                self.unregister_command_set(self._vegetables)
                self.poutput('Vegetables unloaded')

        cut_parser = cmd2.Cmd2ArgumentParser()
        cut_subparsers = cut_parser.add_subparsers(title='item', help='item to cut')

        @with_argparser(cut_parser)
        def do_cut(self, ns: argparse.Namespace):
            handler = ns.cmd2_handler.get()
            if handler is not None:
                # Call whatever subcommand function was selected
                handler(ns)
            else:
                # No subcommand was provided, so call help
                self.poutput('This command does nothing without sub-parsers registered')
                self.do_help('cut')


    if __name__ == '__main__':
        app = ExampleApp()
        app.cmdloop()
