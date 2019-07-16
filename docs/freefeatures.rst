===================================
Features requiring no modifications
===================================

These features are provided "for free" to a cmd_-based application
simply by replacing ``import cmd`` with ``import cmd2 as cmd``.

.. _cmd: https://docs.python.org/3/library/cmd.html

.. _scripts:

Script files
============

Text files can serve as scripts for your ``cmd2``-based application, with the
``run_script``, ``_relative_run_script``, and ``edit`` commands.

Both ASCII and UTF-8 encoded unicode text files are supported.

Simply include one command per line, typed exactly as you would inside a
``cmd2`` application.

.. automethod:: cmd2.cmd2.Cmd.do_run_script
    :noindex:

.. automethod:: cmd2.cmd2.Cmd.do__relative_run_script
    :noindex:

.. automethod:: cmd2.cmd2.Cmd.do_edit
    :noindex:


Startup Initialization Script
=============================

You can execute commands from a startup initialization script by passing a file
path to the ``startup_script`` argument to the ``cmd2.Cmd.__init__()`` method
like so::

    class StartupApp(cmd2.Cmd):
        def __init__(self):
            cmd2.Cmd.__init__(self, startup_script='.cmd2rc')

See the AliasStartup_ example for a demonstration.

.. _AliasStartup: https://github.com/python-cmd2/cmd2/blob/master/examples/alias_startup.py

Commands at invocation
======================

You can send commands to your app as you invoke it by
including them as extra arguments to the program.
``cmd2`` interprets each argument as a separate
command, so you should enclose each command in
quotation marks if it is more than a one-word command.

::

  cat@eee:~/proj/cmd2/example$ python example.py "say hello" "say Gracie" quit
  hello
  Gracie
  cat@eee:~/proj/cmd2/example$

.. note::

   If you wish to disable cmd2's consumption of command-line arguments, you can do so by setting the  ``allow_cli_args``
   argument of your ``cmd2.Cmd`` class instance to ``False``.  This would be useful, for example, if you wish to use
   something like Argparse_ to parse the overall command line arguments for your application::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               super().__init__(allow_cli_args=False)

.. _Argparse: https://docs.python.org/3/library/argparse.html

.. _output_redirection:



Quitting the application
========================

``cmd2`` pre-defines a ``quit`` command for you.
It's trivial, but it's one less thing for you to remember.


Misc. pre-defined commands
==========================

Several generically useful commands are defined
with automatically included ``do_`` methods.

.. automethod:: cmd2.cmd2.Cmd.do_quit
    :noindex:

.. automethod:: cmd2.cmd2.Cmd.do_shell
    :noindex:

( ``!`` is a shortcut for ``shell``; thus ``!ls``
is equivalent to ``shell ls``.)


Tab-Completion
==============

``cmd2`` adds tab-completion of file system paths for all built-in commands
where it makes sense, including:

- ``edit``
- ``run_pyscript``
- ``run_script``
- ``shell``

``cmd2`` also adds tab-completion of shell commands to the ``shell`` command.

Additionally, it is trivial to add identical file system path completion to
your own custom commands.  Suppose you have defined a custom command ``foo`` by
implementing the ``do_foo`` method.  To enable path completion for the ``foo``
command, then add a line of code similar to the following to your class which
inherits from ``cmd2.Cmd``::

    complete_foo = self.path_complete

This will effectively define the ``complete_foo`` readline completer method in
your class and make it utilize the same path completion logic as the built-in
commands.

The built-in logic allows for a few more advanced path completion capabilities,
such as cases where you only want to match directories.  Suppose you have a
custom command ``bar`` implemented by the ``do_bar`` method.  You can enable
path completion of directories only for this command by adding a line of code
similar to the following to your class which inherits from ``cmd2.Cmd``::

    # Make sure you have an "import functools" somewhere at the top
    complete_bar = functools.partialmethod(cmd2.Cmd.path_complete, path_filter=os.path.isdir)
