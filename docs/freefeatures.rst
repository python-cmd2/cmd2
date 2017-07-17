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
application, with the ``load``, ``_relative_load``, ``save``, and ``edit`` commands.

Both ASCII and UTF-8 encoded unicode text files are supported.

Simply include one command per line, typed exactly as you would inside a ``cmd2`` application.

.. automethod:: cmd2.Cmd.do_load

.. automethod:: cmd2.Cmd.do__relative_load

.. automethod:: cmd2.Cmd.do_save

.. automethod:: cmd2.Cmd.do_edit


Comments
========

Comments are omitted from the argument list
before it is passed to a ``do_`` method.  By
default, both Python-style and C-style comments
are recognized; you may change this by overriding
``app.commentGrammars`` with a different pyparsing_
grammar.

Comments can be useful in :ref:`scripts`, but would
be pointless within an interactive session.

::

    def do_speak(self, arg):
        self.stdout.write(arg + '\n')

::

  (Cmd) speak it was /* not */ delicious! # Yuck!
  it was  delicious!

.. _pyparsing: http://pyparsing.wikispaces.com/

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

Output redirection
==================

As in a Unix shell, output of a command can be redirected:

  - sent to a file with ``>``, as in ``mycommand args > filename.txt``
  - piped (``|``) as input to operating-system commands, as in
    ``mycommand args | wc``
  - sent to the paste buffer, ready for the next Copy operation, by
    ending with a bare ``>``, as in ``mycommand args >``..  Redirecting
    to paste buffer requires software to be installed on the operating
    system, pywin32_ on Windows or xclip_ on \*nix.

If your application depends on mathematical syntax, ``>`` may be a bad
choice for redirecting output - it will prevent you from using the
greater-than sign in your actual user commands.  You can override your
app's value of ``self.redirector`` to use a different string for output redirection::

    class MyApp(cmd2.Cmd):
        redirector = '->'

::

    (Cmd) say line1 -> out.txt
    (Cmd) say line2 ->-> out.txt
    (Cmd) !cat out.txt
    line1
    line2

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

.. _pywin32: http://sourceforge.net/projects/pywin32/
.. _xclip: http://www.cyberciti.biz/faq/xclip-linux-insert-files-command-output-intoclipboard/

Python
======

The ``py`` command will run its arguments as a Python
command.  Entered without arguments, it enters an
interactive Python session.  That session can call
"back" to your application with ``cmd("")``.  Through
``self``, it also has access to your application
instance itself which can be extremely useful for debugging.
(If giving end-users this level of introspection is inappropriate,
the ``locals_in_py`` parameter can be set to ``False`` and removed
from the settable dictionary. See see :ref:`parameters`)

::

    (Cmd) py print("-".join("spelling"))
    s-p-e-l-l-i-n-g
    (Cmd) py
    Python 2.6.4 (r264:75706, Dec  7 2009, 18:45:15)
    [GCC 4.4.1] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    (CmdLineApp)

        py <command>: Executes a Python command.
        py: Enters interactive Python mode.
        End with `Ctrl-D` (Unix) / `Ctrl-Z` (Windows), `quit()`, 'exit()`.
        Non-python commands can be issued with `cmd("your command")`.

    >>> import os
    >>> os.uname()
    ('Linux', 'eee', '2.6.31-19-generic', '#56-Ubuntu SMP Thu Jan 28 01:26:53 UTC 2010', 'i686')
    >>> cmd("say --piglatin {os}".format(os=os.uname()[0]))
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

    If you want to be able to pass arguments with spaces to scripts, then we strongly recommend setting the
    cmd2 global variable ``USE_ARG_LIST`` to ``True`` in your application using the ``set_use_arg_list`` function.
    This passes all arguments to ``@options`` commands as a list of strings instead of a single string.

    Once this option is set, you can then put arguments in quotes like so::

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
the up- and down- cursor keys.

All cmd_-based applications on systems with the ``readline`` module
also provide `bash-like history list editing`_.

.. _`bash-like history list editing`: http://www.talug.org/events/20030709/cmdline_history.html

``cmd2`` makes a third type of history access available, consisting of these commands:

.. automethod:: cmd2.Cmd.do_history

.. automethod:: cmd2.Cmd.do_run

Quitting the application
========================

``cmd2`` pre-defines a ``quit`` command for you.
It's trivial, but it's one less thing for you to remember.


Abbreviated commands
====================

``cmd2`` apps will accept shortened command names
so long as there is no ambiguity if the ``abbrev`` settable parameter is set to ``True``.
Thus, if ``do_divide`` is defined, then ``divid``, ``div``,
or even ``d`` will suffice, so long as there are
no other commands defined beginning with *divid*,
*div*, or *d*.

This behavior is disabled by default, but can be turned on with ``app.abbrev`` (see :ref:`parameters`)

.. warning::

    Due to the way the parsing logic works for multiline commands, abbreviations
    will not be accepted for multiline commands.

Misc. pre-defined commands
==========================

Several generically useful commands are defined
with automatically included ``do_`` methods.

.. automethod:: cmd2.Cmd.do_quit

.. automethod:: cmd2.Cmd.do_shell

( ``!`` is a shortcut for ``shell``; thus ``!ls``
is equivalent to ``shell ls``.)


Transcript-based testing
========================

If the entire transcript (input and output) of a successful session of
a ``cmd2``-based app is copied from the screen and pasted into a text
file, ``transcript.txt``, then a transcript test can be run against it::

  python app.py --test transcript.txt

Any non-whitespace deviations between the output prescribed in ``transcript.txt`` and
the actual output from a fresh run of the application will be reported
as a unit test failure.  (Whitespace is ignored during the comparison.)

Regular expressions can be embedded in the transcript inside paired ``/``
slashes.  These regular expressions should not include any whitespace
expressions.

.. note::

   If you have set ``allow_cli_args`` to False in order to disable parsing of command line arguments at invocation,
   then the use of ``-t`` or ``--test`` to run transcript testing is automatically disabled.  In this case, you can
   alternatively provide a value for the optional ``transcript_files`` when constructing the instance of your
   ``cmd2.Cmd`` derived class in order to cause a transcript test to run::

       from cmd2 import Cmd
       class App(Cmd):
         # customized attributes and methods here

       if __name__ == '__main__':
           app = App(transcript_files=['exampleSession.txt'])
           app.cmdloop()


Tab-Completion
==============

``cmd2`` adds tab-completion of file system paths for all built-in commands where it makes sense, including:

- ``edit``
- ``load``
- ``pyscript``
- ``save``
- ``shell``

``cmd2`` also adds tab-completion of shell commands to the ``shell`` command.

Additionally, it is trivial to add identical file system path completion to your own custom commands.  Suppose you
have defined a custom command ``foo`` by implementing the ``do_foo`` method.  To enable path completion for the ``foo``
command, then add a line of code similar to the following to your class which inherits from ``cmd2.Cmd``::

    # Assuming you have an "import cmd2" somewhere at the top
    complete_foo = cmd2.Cmd.path_complete

This will effectively define the ``complete_foo`` readline completer method in your class and make it utilize the same
path completion logic as the built-in commands.

The build-in logic allows for a few more advanced path completion capabilities, such as cases where you only want to
match directories.  Suppose you have a custom command ``bar`` implemented by the ``do_bar`` method.  YOu can enable
path completion of directories only for this command by adding a line of code similar to the following to your class
which inherits from ``cmd2.Cmd``::

    # Make sure you have an "import functools" somewhere at the top
    complete_bar = functools.partialmethod(cmd2.Cmd.path_complete, dir_only=True)
