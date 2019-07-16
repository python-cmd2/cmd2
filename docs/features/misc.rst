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
