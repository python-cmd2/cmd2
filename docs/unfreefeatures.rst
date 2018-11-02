======================================
Features requiring application changes
======================================

Multiline commands
==================

Command input may span multiple lines for the
commands whose names are listed in the
parameter ``app.multiline_commands``.  These
commands will be executed only
after the user has entered a *terminator*.
By default, the command terminator is
``;``; replacing or appending to the list
``app.terminators`` allows different
terminators.  A blank line
is *always* considered a command terminator
(cannot be overridden).

In multiline commands, output redirection characters
like ``>`` and ``|`` are part of the command
arguments unless they appear after the terminator.


Parsed statements
=================

``cmd2`` passes ``arg`` to a ``do_`` method (or
``default``) as a Statement, a subclass of
string that includes many attributes of the parsed
input:

command
    Name of the command called

args
    The arguments to the command with output redirection
    or piping to shell commands removed

command_and_args
    A string of just the command and the arguments, with
    output redirection or piping to shell commands removed

argv
    A list of arguments a-la ``sys.argv``, including
    the command as ``argv[0]`` and the subsequent
    arguments as additional items in the list.
    Quotes around arguments will be stripped as will
    any output redirection or piping portions of the command

raw
    Full input exactly as typed.

terminator
    Character used to end a multiline command



If ``Statement`` does not contain an attribute,
querying for it will return ``None``.

(Getting ``arg`` as a ``Statement`` is
technically "free", in that it requires no application
changes from the cmd_ standard, but there will
be no result unless you change your application
to *use* any of the additional attributes.)

.. _cmd: https://docs.python.org/3/library/cmd.html


Environment parameters
======================

Your application can define user-settable parameters which your code can
reference. First create a class attribute with the default value. Then
update the ``settable`` dictionary with your setting name and a short
description before you initialize the superclass. Here's an example, from
``examples/environment.py``:

.. literalinclude:: ../examples/environment.py

If you want to be notified when a setting changes (as we do above), then
define a method ``_onchange_{setting}()``. This method will be called after
the user changes a setting, and will receive both the old value and the new
value.

.. code-block:: none

   (Cmd) set --long | grep sunny
   sunny: False                # Is it sunny outside?
   (Cmd) set --long | grep degrees
   degrees_c: 22               # Temperature in Celsius
   (Cmd) sunbathe
   Too dim.
   (Cmd) set degrees_c 41
   degrees_c - was: 22
   now: 41
   (Cmd) set sunny
   sunny: True
   (Cmd) sunbathe
   UV is bad for your skin.
   (Cmd) set degrees_c 13
   degrees_c - was: 41
   now: 13
   (Cmd) sunbathe
   It's 13 C - are you a penguin?


Commands with flags
===================

All ``do_`` methods are responsible for interpreting
the arguments passed to them.  However, ``cmd2`` lets
a ``do_`` methods accept Unix-style *flags*.  It uses argparse_
to parse the flags, and they work the same way as for
that module.

``cmd2`` defines a few decorators which change the behavior of
how arguments get parsed for and passed to a ``do_`` method.  See the section :ref:`decorators` for more information.

.. _argparse: https://docs.python.org/3/library/argparse.html

poutput, pfeedback, perror, ppaged
==================================

Standard ``cmd`` applications produce their output with ``self.stdout.write('output')`` (or with ``print``,
but ``print`` decreases output flexibility).  ``cmd2`` applications can use
``self.poutput('output')``, ``self.pfeedback('message')``, ``self.perror('errmsg')``, and ``self.ppaged('text')``
instead.  These methods have these advantages:

- Handle output redirection to file and/or pipe appropriately
- More concise
    - ``.pfeedback()`` destination is controlled by :ref:`quiet` parameter.
- Option to display long output using a pager via ``ppaged()``

.. automethod:: cmd2.cmd2.Cmd.poutput
.. automethod:: cmd2.cmd2.Cmd.perror
.. automethod:: cmd2.cmd2.Cmd.pfeedback
.. automethod:: cmd2.cmd2.Cmd.ppaged


Colored Output
==============

The output methods in the previous section all honor the ``colors`` setting,
which has three possible values:

Never
    poutput(), pfeedback(), and ppaged() strip all ANSI escape sequences
    which instruct the terminal to colorize output

Terminal
    (the default value) poutput(), pfeedback(), and ppaged() do not strip any
    ANSI escape sequences when the output is a terminal, but if the output is
    a pipe or a file the escape sequences are stripped. If you want colorized
    output you must add ANSI escape sequences, preferably using some python
    color library like `plumbum.colors`, `colorama`, `blessings`, or
    `termcolor`.

Always
    poutput(), pfeedback(), and ppaged() never strip ANSI escape sequences,
    regardless of the output destination


.. _quiet:

Suppressing non-essential output
================================

The ``quiet`` setting controls whether ``self.pfeedback()`` actually produces
any output. If ``quiet`` is ``False``, then the output will be produced. If
``quiet`` is ``True``, no output will be produced.

This makes ``self.pfeedback()`` useful for non-essential output like status
messages. Users can control whether they would like to see these messages by changing
the value of the ``quiet`` setting.


select
======

Presents numbered options to user, as bash ``select``.

``app.select`` is called from within a method (not by the user directly; it is ``app.select``, not ``app.do_select``).

.. automethod:: cmd2.cmd2.Cmd.select

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


Exit code to shell
==================
The ``self.exit_code`` attribute of your ``cmd2`` application controls
what exit code is sent to the shell when your application exits from
``cmdloop()``.


Asynchronous Feedback
=====================
``cmd2`` provides two functions to provide asynchronous feedback to the user without interfering with
the command line. This means the feedback is provided to the user when they are still entering text at
the prompt. To use this functionality, the application must be running in a terminal that supports
VT100 control characters and readline. Linux, Mac, and Windows 10 and greater all support these.

async_alert()
    Used to display an important message to the user while they are at the prompt in between commands.
    To the user it appears as if an alert message is printed above the prompt and their current input
    text and cursor location is left alone.

async_update_prompt()
    Updates the prompt while the user is still typing at it. This is good for alerting the user to system
    changes dynamically in between commands. For instance you could alter the color of the prompt to indicate
    a system status or increase a counter to report an event.

``cmd2`` also provides a function to change the title of the terminal window. This feature requires the
application be running in a terminal that supports VT100 control characters. Linux, Mac, and Windows 10 and
greater all support these.

set_window_title()
    Sets the terminal window title


The easiest way to understand these functions is to see the AsyncPrinting_ example for a demonstration.

.. _AsyncPrinting: https://github.com/python-cmd2/cmd2/blob/master/examples/async_printing.py
