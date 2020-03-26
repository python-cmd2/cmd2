Miscellaneous Features
======================


Timer
-----

Turn the timer setting on, and ``cmd2`` will show the wall time it takes for
each command to execute.


Exiting
-------

Mention quit, and EOF handling built into ``cmd2``.


select
------

Presents numbered options to user, as bash ``select``.

``app.select`` is called from within a method (not by the user directly; it is
``app.select``, not ``app.do_select``).

.. automethod:: cmd2.Cmd.select
    :noindex:

::

    def do_eat(self, arg):
        sauce = self.select('sweet salty', 'Sauce? ')
        result = '{food} with {sauce} sauce, yum!'
        result = result.format(food=arg, sauce=sauce)
        self.stdout.write(result + '\n')

::

    (Cmd) eat wheaties
        1. sweet
        2. salty
    Sauce? 2
    wheaties with salty sauce, yum!


Disabling Commands
------------------

``cmd2`` supports disabling commands during runtime. This is useful if certain
commands should only be available when the application is in a specific state.
When a command is disabled, it will not show up in the help menu or tab
complete. If a user tries to run the command, a command-specific message
supplied by the developer will be printed. The following functions support this
feature.

enable_command()
    Enable an individual command

enable_category()
    Enable an entire category of commands

disable_command()
    Disable an individual command and set the message that will print when this
    command is run or help is called on it while disabled

disable_category()
    Disable an entire category of commands and set the message that will print
    when anything in this category is run or help is called on it while
    disabled

See the definitions of these functions for descriptions of their arguments.

See the ``do_enable_commands()`` and ``do_disable_commands()`` functions in the
HelpCategories_ example for a demonstration.

.. _HelpCategories: https://github.com/python-cmd2/cmd2/blob/master/examples/help_categories.py


Default to shell
----------------

Every ``cmd2`` application can execute operating-system level (shell) commands
with ``shell`` or a ``!`` shortcut::

  (Cmd) shell which python
  /usr/bin/python
  (Cmd) !which python
  /usr/bin/python

However, if the parameter ``default_to_shell`` is ``True``, then *every*
command will be attempted on the operating system.  Only if that attempt fails
(i.e., produces a nonzero return value) will the application's own ``default``
method be called.

::

  (Cmd) which python
  /usr/bin/python
  (Cmd) my dog has fleas
  sh: my: not found
  *** Unknown syntax: my dog has fleas


Quit on SIGINT
--------------

On many shells, SIGINT (most often triggered by the user pressing Ctrl+C)
while at the prompt only cancels the current line, not the entire command
loop. By default, a ``cmd2`` application matches this behavior. However, if
``quit_on_sigint`` is set to ``True``, the command loop will quit instead.

::

  (Cmd) typing a comma^C
  (Cmd)

.. warning::
    The default SIGINT behavior will only function properly if **cmdloop** is running
    in the main thread.
