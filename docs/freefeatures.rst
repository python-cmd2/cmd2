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
application, with the ``load``, ``save``, and ``edit``
commands.

.. automethod:: cmd2.Cmd.do_load

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
interactive Python session, this shell can access your application instance via ``self``.
However, the ``ipy`` shell cannot call "back" to your application with ``cmd("")`` and
any changes made will not persist between sessions or back in the main application.

IPython_ provides many advantages, including:

    * Comprehensive object introspection
    * Input history, persistent across sessions
    * Caching of output results during a session with automatically generated references
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

.. automethod:: cmd2.Cmd.do_list

.. automethod:: cmd2.Cmd.do_run

Quitting the application
========================

``cmd2`` pre-defines a ``quit`` command for you.
It's trivial, but it's one less thing for you to remember.


Abbreviated commands
====================

``cmd2`` apps will accept shortened command names
so long as there is no ambiguity.  Thus, if
``do_divide`` is defined, then ``divid``, ``div``,
or even ``d`` will suffice, so long as there are
no other commands defined beginning with *divid*,
*div*, or *d*.

This behavior can be turned off with ``app.abbrev`` (see :ref:`parameters`)

Misc. pre-defined commands
==========================

Several generically useful commands are defined
with automatically included ``do_`` methods.

.. automethod:: cmd2.Cmd.do_quit

.. automethod:: cmd2.Cmd.do_pause

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

