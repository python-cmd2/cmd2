Generating Output
=================

A standard ``cmd`` application can produce output by using either of these
methods::

  print("Greetings, Professor Falken.", file=self.stdout)
  self.stdout.write("Shall we play a game?\n")

While you could send output directly to ``sys.stdout``, :mod:`cmd2.Cmd`
can be initialized with a ``stdin`` and ``stdout`` variables, which it stores
as ``self.stdin`` and ``self.stdout``. By using these variables every time you
produce output, you can trivially change where all the output goes by changing
how you initialize your class.

:mod:`cmd2.Cmd` extends this approach in a number of convenient ways. See
:ref:`features/redirection:Output Redirection And Pipes` for information on how
users can change where the output of a command is sent. In order for those
features to work, the output you generate must be sent to ``self.stdout``. You
can use the methods described above, and everything will work fine.
:mod:`cmd2.Cmd` also includes a number of output related methods which you
may use to enhance the output your application produces.


Ordinary Output
---------------

The :meth:`~cmd2.Cmd.poutput` method is similar to the Python
`built-in print function <https://docs.python.org/3/library/functions.html#print>`_. :meth:`~cmd2.Cmd.poutput` adds two
conveniences:

  1. Since users can pipe output to a shell command, it catches
  ``BrokenPipeError`` and outputs the contents of
  ``self.broken_pipe_warning`` to ``stderr``. ``self.broken_pipe_warning``
  defaults to an empty string so this method will just swallow the exception.
  If you want to show an error message, put it in
  ``self.broken_pipe_warning`` when you initialize :mod:`~cmd2.Cmd`.

  2. It examines and honors the :ref:`features/settings:allow_style` setting.
  See :ref:`features/generating_output:Colored Output` below for more details.

Here's a simple command that shows this method in action::

    def do_echo(self, args):
        """A simple command showing how poutput() works"""
        self.poutput(args)


Error Messages
--------------

When an error occurs in your program, you can display it on ``sys.stderr`` by
calling the :meth:`~.cmd2.Cmd.perror` method. By default this method applies
:meth:`cmd2.ansi.style_error` to the output.


Warning Messages
----------------

:meth:`~.cmd2.Cmd.pwarning` is just like :meth:`~.cmd2.Cmd.perror` but applies
:meth:`cmd2.ansi.style_warning` to the output.


Feedback
--------

You may have the need to display information to the user which is not intended
to be part of the generated output. This could be debugging information or
status information about the progress of long running commands. It's not
output, it's not error messages, it's feedback. If you use the
:ref:`features/settings:Timing` setting, the output of how long it took the
command to run will be output as feedback. You can use the
:meth:`~.cmd2.Cmd.pfeedback` method to produce this type of output, and
several :ref:`features/settings:Settings` control how it is handled.

If the :ref:`features/settings:quiet` setting is ``True``, then calling
:meth:`~.cmd2.Cmd.pfeedback` produces no output. If
:ref:`features/settings:quiet` is ``False``, the
:ref:`features/settings:feedback_to_output` setting is consulted to determine
whether to send the output to ``stdout`` or ``stderr``.


Exceptions
----------

If your app catches an exception and you would like to display the exception to
the user, the :meth:`~.cmd2.Cmd.pexcept` method can help. The default behavior
is to just display the message contained within the exception. However, if the
:ref:`features/settings:debug` setting is ``True``, then the entire stack trace
will be displayed.


Paging Output
-------------

If you know you are going to generate a lot of output, you may want to display
it in a way that the user can scroll forwards and backwards through it. If you
pass all of the output to be displayed in a single call to
:meth:`~.cmd2.Cmd.ppaged`, it will be piped to an operating system appropriate
shell command to page the output. On Windows, the output is piped to ``more``;
on Unix-like operating systems like MacOS and Linux, it is piped to ``less``.


Colored Output
--------------

You can add your own `ANSI escape sequences
<https://en.wikipedia.org/wiki/ANSI_escape_code#Colors>`_ to your output which
tell the terminal to change the foreground and background colors. If you want
to give yourself a headache, you can generate these by hand. You could also use
a Python color library like `plumbum.colors
<https://plumbum.readthedocs.io/en/latest/colors.html>`_, `colored
<https://gitlab.com/dslackw/colored>`_, or `colorama
<https://github.com/tartley/colorama>`_. Colorama is unique because when it's
running on Windows, it wraps ``stdout``, looks for ANSI escape sequences, and
converts them into the appropriate ``win32`` calls to modify the state of the
terminal.

``cmd2`` imports and uses Colorama and provides a number of convenience methods
for generating colorized output, measuring the screen width of colorized
output, setting the window title in the terminal, and removing ANSI text style
escape codes from a string. These functions are all documentated in
:mod:`cmd2.ansi`.

After adding the desired escape sequences to your output, you should use one of
these methods to present the output to the user:

- :meth:`.cmd2.Cmd.poutput`
- :meth:`.cmd2.Cmd.perror`
- :meth:`.cmd2.Cmd.pwarning`
- :meth:`.cmd2.Cmd.pexcept`
- :meth:`.cmd2.Cmd.pfeedback`
- :meth:`.cmd2.Cmd.ppaged`

These methods all honor the :ref:`features/settings:allow_style` setting, which
users can modify to control whether these escape codes are passed through to
the terminal or not.


Aligning Text
--------------

If you would like to generate output which is left, center, or right aligned
within a specified width or the terminal width, the following functions can
help:

- :meth:`cmd2.utils.align_left`
- :meth:`cmd2.utils.align_center`
- :meth:`cmd2.utils.align_right`

These functions differ from Python's string justifying functions in that they
support characters with display widths greater than 1. Additionally, ANSI style
sequences are safely ignored and do not count toward the display width. This
means colored text is supported. If text has line breaks, then each line is
aligned independently.



Columnar Output
---------------

When generating output in multiple columns, you often need to calculate the
width of each item so you can pad it appropriately with spaces. However, there
are categories of Unicode characters that occupy 2 cells, and other that occupy
0. To further complicate matters, you might have included ANSI escape sequences
in the output to generate colors on the terminal.

The :meth:`cmd2.ansi.style_aware_wcswidth` function solves both of these
problems. Pass it a string, and regardless of which Unicode characters and ANSI
text style escape sequences it contains, it will tell you how many characters
on the screen that string will consume when printed.
