Plugins
=======

``cmd2`` has a built-in plugin framework which allows developers to create a
a ``cmd2`` plugin which can extend basic ``cmd2`` functionality and can be
used by multiple applications.

There are many ways to add functionality to ``cmd2`` using a plugin. Most
plugins will be implemented as a mixin. A mixin is a class that encapsulates
and injects code into another class. Developers who use a plugin in their
``cmd2`` project will inject the plugin's code into their subclass of
:class:`cmd2.Cmd`.


Mixin and Initialization
------------------------

The following short example shows how to mix in a plugin and how the plugin
gets initialized.

Here's the plugin::

    class MyPlugin:
        def __init__(self, *args, **kwargs):
            # code placed here runs before cmd2.Cmd initializes
            super().__init__(*args, **kwargs)
            # code placed here runs after cmd2.Cmd initializes

and an example app which uses the plugin::

    import cmd2
    import cmd2_myplugin

    class Example(cmd2_myplugin.MyPlugin, cmd2.Cmd):
        """An class to show how to use a plugin"""
        def __init__(self, *args, **kwargs):
            # code placed here runs before cmd2.Cmd or
            # any plugins initialize
            super().__init__(*args, **kwargs)
            # code placed here runs after cmd2.Cmd and
            # all plugins have initialized

Note how the plugin must be inherited (or mixed in) before :class:`cmd2.Cmd`.
This is required for two reasons:

- The ``cmd.Cmd.__init__`` method in the python standard library does not
  call ``super().__init__()``. Because of this oversight, if you don't
  inherit from ``MyPlugin`` first, the ``MyPlugin.__init__()`` method will
  never be called.
- You may want your plugin to be able to override methods from
  :class:`cmd2.Cmd`. If you mixin the plugin after ``cmd2.Cmd``, the python
  method resolution order will call :class:`cmd2.Cmd` methods before it calls
  those in your plugin.


Add commands
------------

Your plugin can add user visible commands. You do it the same way in a plugin
that you would in a :class:`cmd2.Cmd` app::

    class MyPlugin:
        def do_say(self, statement):
            """Simple say command"""
            self.poutput(statement)

You have all the same capabilities within the plugin that you do inside a
:class:`cmd2.Cmd` app, including argument parsing via decorators and custom
help methods.


Add (or hide) settings
----------------------

A plugin may add user controllable settings to the application. Here's an
example::

    class MyPlugin:
        def __init__(self, *args, **kwargs):
            # code placed here runs before cmd2.Cmd initializes
            super().__init__(*args, **kwargs)
            # code placed here runs after cmd2.Cmd initializes
            self.mysetting = 'somevalue'
            self.add_settable(cmd2.Settable('mysetting', str, 'short help message for mysetting', self))

You can hide settings from the user by calling
:meth:`~cmd2.Cmd.remove_settable`. See :ref:`features/settings:Settings` for
more information.


Decorators
----------

Your plugin can provide a decorator which users of your plugin can use to
wrap functionality around their own commands.


Override methods
----------------

Your plugin can override core :class:`cmd2.Cmd` methods, changing their
behavior. This approach should be used sparingly, because it is very brittle.
If a developer chooses to use multiple plugins in their application, and
several of the plugins override the same method, only the first plugin to be
mixed in will have the overridden method called.

Hooks are a much better approach.


Hooks
-----

Plugins can register hook methods, which are called by :class:`cmd2.Cmd`
during various points in the application and command processing lifecycle.
Plugins should not override any of the deprecated hook methods, instead they
should register their hooks as described in the :ref:`features/hooks:Hooks`
section.

You should name your hooks so that they begin with the name of your plugin.
Hook methods get mixed into the ``cmd2`` application and this naming
convention helps avoid unintentional method overriding.

Here's a simple example::

    class MyPlugin:
        def __init__(self, *args, **kwargs):
            # code placed here runs before cmd2 initializes
            super().__init__(*args, **kwargs)
            # code placed here runs after cmd2 initializes
            # this is where you register any hook functions
            self.register_postparsing_hook(self.cmd2_myplugin_postparsing_hook)

        def cmd2_myplugin_postparsing_hook(self, data: cmd2.plugin.PostparsingData) -> cmd2.plugin.PostparsingData:
            """Method to be called after parsing user input, but before running the command"""
            self.poutput('in postparsing_hook')
            return data

Registration allows multiple plugins (or even the application itself) to each
inject code to be called during the application or command processing
lifecycle.

See the :ref:`features/hooks:Hooks` documentation for full details of the
application and command lifecycle, including all available hooks and the
ways hooks can influence the lifecycle.


Classes and Functions
---------------------

Your plugin can also provide classes and functions which can be used by
developers of ``cmd2`` based applications. Describe these classes and
functions in your documentation so users of your plugin will know what's
available.


Examples
--------

See `<https://github.com/python-cmd2/cmd2-plugin-template>`_ for more info.
