Disabling Commands
==================

``cmd2`` allows a developer to:

- remove commands included in ``cmd2``
- prevent commands from appearing in the help menu (hide commands)
- disable and re-enable commands at runtime


Remove A Command
----------------

When a command has been removed, the command method has been deleted from the
object. The command doesn't show up in help, and it can't be executed. This
approach is appropriate if you never want a built-in command to be part of your
application. Delete the command method in your initialization code::

    class RemoveBuiltinCommand(cmd2.Cmd):
        """An app which removes a built-in command from cmd2"""

        def __init__(self):
            super().__init__()
            # To remove built-in commands entirely, delete
            # the "do_*" function from the cmd2.Cmd class
            del cmd2.Cmd.do_edit


Hide A Command
--------------

When a command is hidden, it won't show up in the help menu, but if
the user knows it's there and types the command, it will be executed.
You hide a command by adding it to the ``hidden_commands`` list::

    class HiddenCommands(cmd2.Cmd):
        ""An app which demonstrates how to hide a command"""
        def __init__(self):
            super().__init__()
            self.hidden_commands.append('py')

As shown above, you would typically do this as part of initializing your
application. If you decide you want to unhide a command later in the execution
of your application, you can by doing::

    self.hidden_commands = [cmd for cmd in self.hidden_commands if cmd != 'py']

You might be thinking that the list comprehension is overkill and you'd rather
do something like::

    self.hidden_commands.remove('py')

You may be right, but ``remove()`` will raise a ``ValueError`` if ``py``
isn't in the list, and it will only remove the first one if it's in the list
multiple times.


Disable A Command
-----------------

One way to disable a command is to add code to the command method which
determines whether the command should be executed or not. If the command should
not be executed, your code can print an appropriate error message and return.

``cmd2`` also provides another way to accomplish the same thing. Here's a
simple app which disables the ``open`` command if the door is locked::

    class DisabledCommands(cmd2.Cmd):
        """An application which disables and enables commands"""

        def do_lock(self, line):
            self.disable_command('open', "you can't open the door because it is locked")
            self.poutput('the door is locked')

        def do_unlock(self, line):
            self.enable_command('open')
            self.poutput('the door is unlocked')

        def do_open(self, line):
            """open the door"""
            self.poutput('opening the door')

This method has the added benefit of removing disabled commands from the help
menu. But, this method only works if you know in advance that the command
should be disabled, and if the conditions for re-enabling it are likewise known
in advance.


Disable A Category of Commands
------------------------------

You can group or categorize commands as shown in
:ref:`features/help:Categorizing Commands`. If you do so, you can disable and
enable all the commands in a category with a single method call. Say you have
created a category of commands called "Server Information". You can disable
all commands in that category::

    not_connected_msg = 'You must be connected to use this command'
    self.disable_category('Server Information', not_connected_msg)

Similarly, you can re-enable all the commands in a category::

    self.enable_category('Server Information')
