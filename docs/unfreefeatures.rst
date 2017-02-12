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

Your application can define user-settable parameters
which your code can reference.  Create them as class attributes
with their default values, and add them (with optional
documentation) to ``settable``.

::

    from cmd2 import Cmd
    class App(Cmd):
        degrees_c = 22
        sunny = False
        settable = Cmd.settable + '''degrees_c temperature in Celsius
            sunny'''
        def do_sunbathe(self, arg):
            if self.degrees_c < 20:
                result = "It's {temp} C - are you a penguin?".format(temp=self.degrees_c)
            elif not self.sunny:
                result = 'Too dim.'
            else:
                result = 'UV is bad for your skin.'
            self.stdout.write(result + '\n')
    app = App()
    app.cmdloop()

::

    (Cmd) set --long
    degrees_c: 22                  # temperature in Celsius
    sunny: False                   #
    (Cmd) sunbathe
    Too dim.
    (Cmd) set sunny yes
    sunny - was: False
    now: True
    (Cmd) sunbathe
    UV is bad for your skin.
    (Cmd) set degrees_c 13
    degrees_c - was: 22
    now: 13
    (Cmd) sunbathe
    It's 13 C - are you a penguin?


Commands with flags
===================

All ``do_`` methods are responsible for interpreting
the arguments passed to them.  However, ``cmd2`` lets
a ``do_`` methods accept Unix-style *flags*.  It uses optparse_
to parse the flags, and they work the same way as for
that module.

Flags are defined with the ``options`` decorator,
which is passed a list of optparse_-style options,
each created with ``make_option``.  The method
should accept a second argument, ``opts``, in
addition to ``args``; the flags will be stripped
from ``args``.

::

    @options([make_option('-p', '--piglatin', action="store_true", help="atinLay"),
        make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
        make_option('-r', '--repeat', type="int", help="output [n] times")
    ])
    def do_speak(self, arg, opts=None):
        """Repeats what you tell me to."""
        arg = ''.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:].rstrip(), arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(arg)
            self.stdout.write('\n')

::

    (Cmd) say goodnight, gracie
    goodnight, gracie
    (Cmd) say -sp goodnight, gracie
    OODNIGHT, GRACIEGAY
    (Cmd) say -r 2 --shout goodnight, gracie
    GOODNIGHT, GRACIE
    GOODNIGHT, GRACIE

``options`` takes an optional additional argument, ``arg_desc``.
If present, ``arg_desc`` will appear in place of ``arg`` in
the option's online help.

::

    @options([make_option('-t', '--train', action='store_true', help='by train')],
             arg_desc='(from city) (to city)')
    def do_travel(self, arg, opts=None):
        'Gets you from (from city) to (to city).'


::

    (Cmd) help travel
    Gets you from (from city) to (to city).
    Usage: travel [options] (from-city) (to-city)

    Options:
      -h, --help   show this help message and exit
      -t, --train  by train

Controlling how arguments are parsed for commands with flags
------------------------------------------------------------
There are three functions which can globally effect how arguments are parsed for commands with flags:

.. autofunction:: cmd2.set_posix_shlex

.. autofunction:: cmd2.set_strip_quotes

.. autofunction:: cmd2.set_use_arg_list

.. note::

   Since optparse_ has been deprecated since Python 3.2, the ``cmd2`` developers plan to replace optparse_ with
   argparse_ in the next version of ``cmd2``.  We will endeavor to keep the API as identical as possible when this
   change occurs.

.. _optparse: https://docs.python.org/3/library/optparse.html
.. _argparse: https://docs.python.org/3/library/argparse.html


poutput, pfeedback, perror
==========================

Standard ``cmd`` applications produce their output with ``self.stdout.write('output')`` (or with ``print``,
but ``print`` decreases output flexibility).  ``cmd2`` applications can use
``self.poutput('output')``, ``self.pfeedback('message')``, and ``self.perror('errmsg')``
instead.  These methods have these advantages:

- More concise
    - ``.pfeedback()`` destination is controlled by :ref:`quiet` parameter.


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

