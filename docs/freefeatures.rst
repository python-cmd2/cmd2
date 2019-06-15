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
application, with the ``run_script``, ``_relative_run_script``, and ``edit`` commands.

Both ASCII and UTF-8 encoded unicode text files are supported.

Simply include one command per line, typed exactly as you would inside a ``cmd2`` application.

.. automethod:: cmd2.cmd2.Cmd.do_run_script

.. automethod:: cmd2.cmd2.Cmd.do__relative_run_script

.. automethod:: cmd2.cmd2.Cmd.do_edit


Comments
========

Any command line input where the first non-whitespace character is a `#` will be treated as a comment.
This means any `#` character appearing later in the command will be treated as a literal. The same
applies to a `#` in the middle of a multiline command, even if it is the first character on a line.

Comments can be useful in :ref:`scripts`, but would be pointless within an interactive session.

::

  (Cmd) # this is a comment
  (Cmd) this # is not a comment

Startup Initialization Script
=============================
You can execute commands from a startup initialization script by passing a file path to the ``startup_script``
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
   argument of your ``cmd2.Cmd`` class instance to ``False``.  This would be useful, for example, if you wish to use
   something like Argparse_ to parse the overall command line arguments for your application::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               super().__init__(allow_cli_args=False)

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

The ``app`` object (or your custom name) provides access to application commands
through raw commands.  For example, any application command call be called with
``app("<command>")``.

::

    >>> app('say --piglatin Blah')
    lahBay

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

Using ``py`` to run scripts directly is considered deprecated.  The newer ``run_pyscript`` command
is superior for doing this in two primary ways:

- it supports tab-completion of file system paths
- it has the ability to pass command-line arguments to the scripts invoked

There are no disadvantages to using ``run_pyscript`` as opposed to ``py run()``.  A simple example
of using ``run_pyscript`` is shown below  along with the arg_printer_ script::

    (Cmd) run_pyscript examples/scripts/arg_printer.py foo bar baz
    Running Python script 'arg_printer.py' which was called with 3 arguments
    arg 1: 'foo'
    arg 2: 'bar'
    arg 3: 'baz'

.. note::

    If you want to be able to pass arguments with spaces to commands, then we strongly recommend using one of the decorators,
    such as ``with_argument_list``.  ``cmd2`` will pass your **do_*** methods a list of arguments in this case.

    When using this decorator, you can then put arguments in quotes like so::

        $ examples/arg_print.py
        (Cmd) lprint foo "bar baz"
        lprint was called with the following list of arguments: ['foo', 'bar baz']

.. _arg_printer: https://github.com/python-cmd2/cmd2/blob/master/examples/scripts/arg_printer.py

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

``cmd2`` adds the option of making this history persistent via optional arguments to ``cmd2.Cmd.__init__()``:

.. automethod:: cmd2.cmd2.Cmd.__init__

``cmd2`` makes a third type of history access available with the ``history``
command. Each time the user enters a command, ``cmd2`` saves the input. The
``history`` command lets you do interesting things with that saved input. The
examples to follow all assume that you have entered the following commands::

    (Cmd) alias create one !echo one
    Alias 'one' created
    (Cmd) alias create two !echo two
    Alias 'two' created
    (Cmd) alias create three !echo three
    Alias 'three' created
    (Cmd) alias create four !echo four
    Alias 'four' created

In it's simplest form, the ``history`` command displays previously entered
commands. With no additional arguments, it displays all previously entered
commands::

    (Cmd) history
        1  alias create one !echo one
        2  alias create two !echo two
        3  alias create three !echo three
        4  alias create four !echo four

If you give a positive integer as an argument, then it only displays the
specified command::

    (Cmd) history 4
        4  alias create four !echo four

If you give a negative integer *N* as an argument, then it display the *Nth*
last command. For example, if you give ``-1`` it will display the last command
you entered. If you give ``-2`` it will display the next to last command you
entered, and so forth::

    (Cmd) history -2
        3  alias create three !echo three

You can use a similar mechanism to display a range of commands. Simply give two
command numbers separated by ``..`` or ``:``, and you will see all commands
between, and including, those two numbers::

    (Cmd) history 1:3
        1  alias create one !echo one
        2  alias create two !echo two
        3  alias create three !echo three

If you omit the first number, it will start at the beginning. If you omit the
last number, it will continue to the end::

    (Cmd) history :2
        1  alias create one !echo one
        2  alias create two !echo two
    (Cmd) history 2:
        2  alias create two !echo two
        3  alias create three !echo three
        4  alias create four !echo four

If you want to display the last three commands entered::

    (Cmd) history -- -3:
        2  alias create two !echo two
        3  alias create three !echo three
        4  alias create four !echo four

Notice the double dashes. These are required because the history command uses
``argparse`` to parse the command line arguments. As described in the `argparse
documentation <https://docs.python.org/3/library/argparse.html>`_ , ``-3:`` is
an option, not an argument:

    If you have positional arguments that must begin with - and don’t look like
    negative numbers, you can insert the pseudo-argument '--' which tells
    parse_args() that everything after that is a positional argument:

There is no zeroth command, so don't ask for it. If you are a python programmer,
you've probably noticed this looks a lot like the slice syntax for lists and
arrays. It is, with the exception that the first history command is 1, where the
first element in a python array is 0.

Besides selecting previous commands by number, you can also search for them. You
can use a simple string search::

    (Cmd) history two
        2  alias create two !echo two

Or a regular expression search by enclosing your regex in slashes::

    (Cmd) history '/te\ +th/'
        3  alias create three !echo three

If your regular expression contains any characters that ``argparse`` finds
interesting, like dash or plus, you also need to enclose your regular expression
in quotation marks.

This all sounds great, but doesn't it seem like a bit of overkill to have all
these ways to select commands if all we can do is display them? Turns out,
displaying history commands is just the beginning. The history command can
perform many other actions:

- running previously entered commands
- saving previously entered commands to a text file
- opening previously entered commands in your favorite text editor
- running previously entered commands, saving the commands and their output to a text file
- clearing the history of entered commands

Each of these actions is invoked using a command line option. The ``-r`` or
``--run`` option runs one or more previously entered commands. To run command
number 1::

    (Cmd) history --run 1

To rerun the last two commands (there's that double dash again to make argparse
stop looking for options)::

    (Cmd) history -r -- -2:

Say you want to re-run some previously entered commands, but you would really
like to make a few changes to them before doing so. When you use the ``-e`` or
``--edit`` option, ``history`` will write the selected commands out to a text
file, and open that file with a text editor. You make whatever changes,
additions, or deletions, you want. When you leave the text editor, all the
commands in the file are executed. To edit and then re-run commands 2-4 you
would::

    (Cmd) history --edit 2:4

If you want to save the commands to a text file, but not edit and re-run them,
use the ``-o`` or ``--output-file`` option. This is a great way to create
:ref:`scripts`, which can be executed using the ``run_script`` command. To
save the first 5 commands entered in this session to a text file::

    (Cmd) history :5 -o history.txt

The ``history`` command can also save both the commands and their output to a
text file. This is called a transcript. See :doc:`transcript` for more
information on how transcripts work, and what you can use them for. To create a
transcript use the ``-t`` or ``--transcription`` option::

    (Cmd) history 2:3 --transcript transcript.txt

The ``--transcript`` option implies ``--run``: the commands must be re-run in
order to capture their output to the transcript file.

The last action the history command can perform is to clear the command history
using ``-c`` or ``--clear``::

    (Cmd) history -c

In addition to these five actions, the ``history`` command also has some options
to control how the output is formatted. With no arguments, the ``history``
command displays the command number before each command. This is great when
displaying history to the screen because it gives you an easy reference to
identify previously entered commands. However, when creating a script or a
transcript, the command numbers would prevent the script from loading properly.
The ``-s`` or ``--script`` option instructs the ``history`` command to suppress
the line numbers. This option is automatically set by the ``--output-file``,
``--transcript``, and ``--edit`` options. If you want to output the history
commands with line numbers to a file, you can do it with output redirection::

    (Cmd) history 1:4 > history.txt

You might use ``-s`` or ``--script`` on it's own if you want to display history
commands to the screen without line numbers, so you can copy them to the
clipboard::

    (Cmd) history -s 1:3

``cmd2`` supports both aliases and macros, which allow you to substitute a
short, more convenient input string with a longer replacement string. Say we
create an alias like this, and then use it::

    (Cmd) alias create ls shell ls -aF
    Alias 'ls' created
    (Cmd) ls -d h*
    history.txt     htmlcov/

By default, the ``history`` command shows exactly what we typed::

    (Cmd) history
        1  alias create ls shell ls -aF
        2  ls -d h*

There are two ways to modify that display so you can see what aliases and macros
were expanded to. The first is to use ``-x`` or ``--expanded``. These options
show the expanded command instead of the entered command::

    (Cmd) history -x
        1  alias create ls shell ls -aF
        2  shell ls -aF -d h*

If you want to see both the entered command and the expanded command, use the
``-v`` or ``--verbose`` option::

    (Cmd) history -v
        1  alias create ls shell ls -aF
        2  ls -d h*
        2x shell ls -aF -d h*

If the entered command had no expansion, it is displayed as usual. However, if
there is some change as the result of expanding macros and aliases, then the
entered command is displayed with the number, and the expanded command is
displayed with the number followed by an ``x``.

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
- ``run_pyscript``
- ``run_script``
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
