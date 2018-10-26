===================================
Features requiring no modifications
===================================

These features are provided "for free" to a cmd_-based application
simply by replacing ``import cmd`` with ``import cmd2 as cmd``.

.. _cmd: https://docs.python.org/3/library/cmd.html

.. _scripts:

Script files
============

Text files can serve as scripts for your ``cmd2``-based
application, with the ``load``, ``_relative_load``, and ``edit`` commands.

Both ASCII and UTF-8 encoded unicode text files are supported.

Simply include one command per line, typed exactly as you would inside a ``cmd2`` application.

.. automethod:: cmd2.cmd2.Cmd.do_load

.. automethod:: cmd2.cmd2.Cmd.do__relative_load

.. automethod:: cmd2.cmd2.Cmd.do_edit


Comments
========

Comments are omitted from the argument list
before it is passed to a ``do_`` method.  By
default, both Python-style and C-style comments
are recognized. Comments can be useful in :ref:`scripts`, but would
be pointless within an interactive session.

::

    def do_speak(self, arg):
        self.stdout.write(arg + '\n')

::

  (Cmd) speak it was /* not */ delicious! # Yuck!
  it was  delicious!

.. _arg_print: https://github.com/python-cmd2/cmd2/blob/master/examples/arg_print.py

Startup Initialization Script
=============================
You can load and execute commands from a startup initialization script by passing a file path to the ``startup_script``
argument to the ``cmd2.Cmd.__init__()`` method like so::

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
   attribute of your ``cmd2.Cmd`` class instance to ``False``.  This would be useful, for example, if you wish to use
   something like Argparse_ to parse the overall command line arguments for your application::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               self.allow_cli_args = False

.. _Argparse: https://docs.python.org/3/library/argparse.html

.. _output_redirection:

Output redirection
==================

As in a Unix shell, output of a command can be redirected:

  - sent to a file with ``>``, as in ``mycommand args > filename.txt``
  - appended to a file with ``>>``, as in ``mycommand args >> filename.txt``
  - piped (``|``) as input to operating-system commands, as in
    ``mycommand args | wc``
  - sent to the operating system paste buffer, by ending with a bare ``>``, as in ``mycommand args >``. You can even append output to the current contents of the paste buffer by ending your command with ``>>``.


.. note::

   If you wish to disable cmd2's output redirection and pipes features, you can do so by setting the ``allow_redirection``
   attribute of your ``cmd2.Cmd`` class instance to ``False``.  This would be useful, for example, if you want to restrict
   the ability for an end user to write to disk or interact with shell commands for security reasons::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               self.allow_redirection = False

   cmd2's parser will still treat the ``>``, ``>>``, and `|` symbols as output redirection and pipe symbols and will strip
   arguments after them from the command line arguments accordingly.  But output from a command will not be redirected
   to a file or piped to a shell command.

If you need to include any of these redirection characters in your command,
you can enclose them in quotation marks, ``mycommand 'with > in the argument'``.

Python
======

The ``py`` command will run its arguments as a Python command.  Entered without
arguments, it enters an interactive Python session.  The session can call "back"
to your application through the name defined in ``self.pyscript_name`` (defaults
to ``app``).  This wrapper provides access to execute commands in your cmd2
application while maintaining isolation.

You may optionally enable full access to to your application by setting
``locals_in_py`` to ``True``.  Enabling this flag adds ``self`` to the python
session, which is a reference to your Cmd2 application. This can be useful for
debugging your application.  To prevent users from enabling this ability
manually you'll need to remove ``locals_in_py`` from the ``settable`` dictionary.
That session can call

The ``app`` object (or your custom name) provides access to application commands
through either raw commands or through a python API wrapper.  For example, any
application command call be called with ``app("<command>")``. All application
commands are accessible as python objects and functions matching the command
name.  For example, the following are equivalent:

::

    >>> app('say --piglatin Blah')
    lahBay
    >>> app.say("Blah", piglatin=True)
    lahBay


Sub-commands are also supported. The following pairs are equivalent:

::

    >>> app('command subcmd1 subcmd2 param1 --myflag --otherflag 3')
    >>> app.command.subcmd1.subcmd2('param1', myflag=True, otherflag=3)

    >>> app('command subcmd1 param1 subcmd2 param2 --myflag --otherflag 3')
    >>> app.command.subcmd1('param1').subcmd2('param2', myflag=True, otherflag=3)


More Python examples:

::

    (Cmd) py print("-".join("spelling"))
    s-p-e-l-l-i-n-g
    (Cmd) py
    Python 3.5.3 (default, Jan 19 2017, 14:11:04)
    [GCC 6.3.0 20170118] on linux
    Type "help", "copyright", "credits" or "license" for more information.
    (CmdLineApp)

    End with `Ctrl-D` (Unix) / `Ctrl-Z` (Windows), `quit()`, `exit()`.
    Non-python commands can be issued with: app("your command")
    Run python code from external script files with: run("script.py")

    >>> import os
    >>> os.uname()
    ('Linux', 'eee', '2.6.31-19-generic', '#56-Ubuntu SMP Thu Jan 28 01:26:53 UTC 2010', 'i686')
    >>> app("say --piglatin {os}".format(os=os.uname()[0]))
    inuxLay
    >>> self.prompt
    '(Cmd) '
    >>> self.prompt = 'Python was here > '
    >>> quit()
    Python was here >

Using the ``py`` command is tightly integrated with your main ``cmd2`` application
and any variables created or changed will persist for the life of the application::

    (Cmd) py x = 5
    (Cmd) py print(x)
    5

The ``py`` command also allows you to run Python scripts via ``py run('myscript.py')``.
This provides a more complicated and more powerful scripting capability than that
provided by the simple text file scripts discussed in :ref:`scripts`.  Python scripts can include
conditional control flow logic.  See the **python_scripting.py** ``cmd2`` application and
the **script_conditional.py** script in the ``examples`` source code directory for an
example of how to achieve this in your own applications.

Using ``py`` to run scripts directly is considered deprecated.  The newer ``pyscript`` command
is superior for doing this in two primary ways:

- it supports tab-completion of file system paths
- it has the ability to pass command-line arguments to the scripts invoked

There are no disadvantages to using ``pyscript`` as opposed to ``py run()``.  A simple example
of using ``pyscript`` is shown below  along with the **examples/arg_printer.py** script::

    (Cmd) pyscript examples/arg_printer.py foo bar baz
    Running Python script 'arg_printer.py' which was called with 3 arguments
    arg 1: 'foo'
    arg 2: 'bar'
    arg 3: 'baz'

.. note::

    If you want to be able to pass arguments with spaces to scripts, then we strongly recommend using one of the decorators,
    such as ``with_argument_list``.  ``cmd2`` will pass your **do_*** methods a list of arguments in this case.

    When using this decorator, you can then put arguments in quotes like so (NOTE: the ``do_pyscript`` method uses this decorator::

        (Cmd) pyscript examples/arg_printer.py hello '23 fnord'
        Running Python script 'arg_printer.py' which was called with 2 arguments
        arg 1: 'hello'
        arg 2: '23 fnord'


IPython (optional)
==================

**If** IPython_ is installed on the system **and** the ``cmd2.Cmd`` class
is instantiated with ``use_ipython=True``, then the optional ``ipy`` command will
be present::

    from cmd2 import Cmd
    class App(Cmd):
        def __init__(self):
            Cmd.__init__(self, use_ipython=True)

The ``ipy`` command enters an interactive IPython_ session.  Similar to an
interactive Python session, this shell can access your application instance via ``self`` and any changes
to your application made via ``self`` will persist.
However, any local or global variable created within the ``ipy`` shell will not persist.
Within the ``ipy`` shell, you cannot call "back" to your application with ``cmd("")``, however you can run commands
directly like so::

    self.onecmd_plus_hooks('help')

IPython_ provides many advantages, including:

    * Comprehensive object introspection
    * Get help on objects with ``?``
    * Extensible tab completion, with support by default for completion of python variables and keywords

The object introspection and tab completion make IPython particularly efficient for debugging as well as for interactive
experimentation and data analysis.

.. _IPython: http://ipython.readthedocs.io

Searchable command history
==========================

All cmd_-based applications have access to previous commands with
the up- and down- arrow keys.

All cmd_-based applications on systems with the ``readline`` module
also provide `Readline Emacs editing mode`_.  With this you can, for example, use **Ctrl-r** to search backward through
the readline history.

``cmd2`` adds the option of making this readline history persistent via optional arguments to ``cmd2.Cmd.__init__()``:

.. automethod:: cmd2.cmd2.Cmd.__init__

``cmd2`` makes a third type of history access available with the **history** command:

.. automethod:: cmd2.cmd2.Cmd.do_history

.. _`Readline Emacs editing mode`: http://readline.kablamo.org/emacs.html

Quitting the application
========================

``cmd2`` pre-defines a ``quit`` command for you.
It's trivial, but it's one less thing for you to remember.


Misc. pre-defined commands
==========================

Several generically useful commands are defined
with automatically included ``do_`` methods.

.. automethod:: cmd2.cmd2.Cmd.do_quit

.. automethod:: cmd2.cmd2.Cmd.do_shell

( ``!`` is a shortcut for ``shell``; thus ``!ls``
is equivalent to ``shell ls``.)


Transcript-based testing
========================

A transcript is both the input and output of a successful session of a
``cmd2``-based app which is saved to a text file. The transcript can be played
back into the app as a unit test.

.. code-block:: none

   $ python example.py --test transcript_regex.txt
   .
   ----------------------------------------------------------------------
   Ran 1 test in 0.013s

   OK

See :doc:`transcript` for more details.


Tab-Completion
==============

``cmd2`` adds tab-completion of file system paths for all built-in commands where it makes sense, including:

- ``edit``
- ``load``
- ``pyscript``
- ``shell``

``cmd2`` also adds tab-completion of shell commands to the ``shell`` command.

Additionally, it is trivial to add identical file system path completion to your own custom commands.  Suppose you
have defined a custom command ``foo`` by implementing the ``do_foo`` method.  To enable path completion for the ``foo``
command, then add a line of code similar to the following to your class which inherits from ``cmd2.Cmd``::

    complete_foo = self.path_complete

This will effectively define the ``complete_foo`` readline completer method in your class and make it utilize the same
path completion logic as the built-in commands.

The built-in logic allows for a few more advanced path completion capabilities, such as cases where you only want to
match directories.  Suppose you have a custom command ``bar`` implemented by the ``do_bar`` method.  You can enable
path completion of directories only for this command by adding a line of code similar to the following to your class
which inherits from ``cmd2.Cmd``::

    # Make sure you have an "import functools" somewhere at the top
    complete_bar = functools.partialmethod(cmd2.Cmd.path_complete, path_filter=os.path.isdir)
