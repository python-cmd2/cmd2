Miscellaneous Features
======================


Timer
-----

Turn the timer setting on, and ``cmd2`` will show the wall time it takes for
each command to execute.


Exiting
-------

Mention quit, and EOF handling built into ``cmd2``.


Shell Command
-------------

``cmd2`` includes a ``shell`` command which executes it's arguments in the
operating system shell::

    (Cmd) shell ls -al

If you use the default :ref:`features/shortcuts_aliases_macros:Shortcuts`
defined in ``cmd2`` you'll get a ``!`` shortcut for ``shell``, which allows you
to type::

    (Cmd) !ls -al


Commands At Invocation
----------------------

.. _Argparse: https://docs.python.org/3/library/argparse.html

You can send commands to your app as you invoke it by including them as extra
arguments to the program. ``cmd2`` interprets each argument as a separate
command, so you should enclose each command in quotation marks if it is more
than a one-word command.

.. code-block:: shell

  $ python examples/example.py "say hello" "say Gracie" quit
  hello
  Gracie


.. note::

   If you wish to disable cmd2's consumption of command-line arguments, you can
   do so by setting the  ``allow_cli_args`` argument of your ``cmd2.Cmd`` class
   instance to ``False``.  This would be useful, for example, if you wish to
   use something like Argparse_ to parse the overall command line arguments for
   your application::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               super().__init__(allow_cli_args=False)


Initialization Script
---------------------

.. _AliasStartup: https://github.com/python-cmd2/cmd2/blob/master/examples/alias_startup.py

You can execute commands from an initialization script by passing a file
path to the ``startup_script`` argument to the ``cmd2.Cmd.__init__()`` method
like so::

    class StartupApp(cmd2.Cmd):
        def __init__(self):
            cmd2.Cmd.__init__(self, startup_script='.cmd2rc')

This text file should contain a :ref:`Command Script
<features/scripting:Command Scripts>`. See the AliasStartup_ example for a
demonstration.


select
------

Presents numbered options to user, as bash ``select``.

``app.select`` is called from within a method (not by the user directly; it is
``app.select``, not ``app.do_select``).

.. automethod:: cmd2.cmd2.Cmd.select
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


Exit code
---------

The ``self.exit_code`` attribute of your ``cmd2`` application controls what
exit code is returned from ``cmdloop()`` when it completes.  It is your job to
make sure that this exit code gets sent to the shell when your application
exits by calling ``sys.exit(app.cmdloop())``.


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

On many shells, SIGINT (most often triggered by the user pressing Ctrl+C) only
cancels the current line, not the entire command loop. By default, a ``cmd2``
application will quit on receiving this signal. However, if ``quit_on_sigint``
is set to ``False``, then the current line will simply be cancelled.

::

  (Cmd) typing a comma^C
  (Cmd)

.. warning::
    The default SIGINT behavior will only function properly if **cmdloop** is running
    in the main thread.
