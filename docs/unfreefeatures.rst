======================================
Features requiring application changes
======================================

Multiline commands
==================

Command input may span multiple lines for the
commands whose names are listed in the
parameter ``app.multilineCommands``.  These
commands will be executed only
after the user has entered a *terminator*.
By default, the command terminators is
``;``; replacing or appending to the list
``app.terminators`` allows different
terminators.  A blank line
is *always* considered a command terminator
(cannot be overridden).


Parsed statements
=================

``cmd2`` passes ``arg`` to a ``do_`` method (or
``default``) as a ParsedString, a subclass of
string that includes an attribute ``parsed``.
``parsed`` is a ``pyparsing.ParseResults``
object produced by applying a pyparsing_
grammar applied to ``arg``.  It may include:

command
    Name of the command called

raw
    Full input exactly as typed.

terminator
    Character used to end a multiline command

suffix
    Remnant of input after terminator

::

    def do_parsereport(self, arg):
        self.stdout.write(arg.parsed.dump() + '\n')

::

    (Cmd) parsereport A B /* C */ D; E
    ['parsereport', 'A B  D', ';', 'E']
    - args: A B  D
    - command: parsereport
    - raw: parsereport A B /* C */ D; E
    - statement: ['parsereport', 'A B  D', ';']
        - args: A B  D
        - command: parsereport
        - terminator: ;
    - suffix: E
    - terminator: ;

If ``parsed`` does not contain an attribute,
querying for it will return ``None``.  (This
is a characteristic of ``pyparsing.ParseResults``.)

The parsing grammar and process currently employed
by cmd2 is stable, but is likely significantly more
complex than it needs to be.  Future ``cmd2`` releases may
change it somewhat (hopefully reducing complexity).

(Getting ``arg`` as a ``ParsedString`` is
technically "free", in that it requires no application
changes from the cmd_ standard, but there will
be no result unless you change your application
to *use* ``arg.parsed``.)

.. _cmd: https://docs.python.org/3/library/cmd.html

.. _pyparsing: http://pyparsing.wikispaces.com/


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

.. automethod:: cmd2.Cmd.poutput
.. automethod:: cmd2.Cmd.perror
.. automethod:: cmd2.Cmd.pfeedback
.. automethod:: cmd2.Cmd.ppaged


color
=====

Text output can be colored by wrapping it in the ``colorize`` method.

.. automethod:: cmd2.Cmd.colorize

.. _quiet:


quiet
=====

Controls whether ``self.pfeedback('message')`` output is suppressed;
useful for non-essential feedback that the user may not always want
to read.  ``quiet`` is only relevant if
``app.pfeedback`` is sometimes used.


select
======

Presents numbered options to user, as bash ``select``.

``app.select`` is called from within a method (not by the user directly; it is ``app.select``, not ``app.do_select``).

.. automethod:: cmd2.Cmd.select

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

