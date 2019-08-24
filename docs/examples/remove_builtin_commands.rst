Remove Built-in Commands
=========================

``cmd2`` comes with a bunch of built-in commands. These commands add lots of
useful functionality, but you might not want them in your application. You can
either hide these commands, or remove them completely.


Hiding Commands
---------------

When a command is hidden, it is still available to run, but it won't show in
the help menu. To hide a command::

    class HideBuiltinCommand(cmd2.Cmd):
        """Hide a built-in command."""

        def __init__(self):
            super().__init__()

            # To prevent commands from displaying in the help menu
            # add them to the hidden_commands list
            self.hidden_commands.append('py')


Removing Commands
-----------------

You can remove a command from your application is defined in ``cmd2.Cmd`` or
inherited from a :ref:`plugin <features/plugins:Plugins>`. Delete the
command method in your initialization code::

    class RemoveBuiltinCommand(cmd2.Cmd):
        """Remove an undesired built-in command."""

        def __init__(self):
            super().__init__()

            # To remove built-in commands entirely, delete
            # the "do_*" function from the cmd2.Cmd class
            del cmd2.Cmd.do_edit
