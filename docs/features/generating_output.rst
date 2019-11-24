Generating Output
=================

A standard ``cmd`` application can produce output by using either of these
methods::

  print("Greetings, Professor Falken.", file=self.stdout)
  self.stdout.write("Shall we play a game?\n")

While you could send output directly to ``sys.stdout``, ``cmd`` can be
initialized with a ``stdin`` and ``stdout`` variables, which it stores
as ``self.stdin`` and ``self.stdout``. By using these variables every
time you produce output, you can trivially change where all the output
goes by changing how you initialize your class.

``cmd2`` extends this approach in a number of convenient ways. See
:ref:`features/redirection:Output Redirection And Pipes` for information on how
users can change where the output of a command is sent. In order for those
features to work, the output you generate must be sent to ``self.stdout``. You
can use the methods described above, and everything will work fine. ``cmd2``
also adds a number of output related methods to ``Cmd2.Cmd`` which you may use
to enhance the output your application produces.


TODO:


- perror
- pwarning
- pexcept
- ppaging

- column formatting?
- wcswidth?

- exceptions

Ordinary Output
---------------

The ``poutput()`` method is almost like using the Python built-in ``print()``
function. ``poutput()`` adds two conveniences.

Since users can pipe output to a shell command, it catches ``BrokenPipeError``
and outputs the contents of ``self.broken_pipe_warning`` to ``stderr``.
``self.broken_pipe_warning`` defaults to an empty string so this method will
just swallow the exception. If you want to show some error message, put it in
``self.broken_pipe_warning`` when you initialize ``Cmd2.cmd``.

``poutput()`` also honors the :ref:`features/settings:allow_ansi` setting,
which controls whether ANSI escape sequences that instruct the terminal to
colorize output are stripped from the output.


Colored Output
--------------

You may want to generate output in different colors, which is typically done by
adding `ANSI escape sequences
<https://en.wikipedia.org/wiki/ANSI_escape_code#Colors>`_ which tell the
terminal to change the foreground and background colors. If you want to give
yourself a headache, you can generate these by hand. You could also use another
Python color library like `plumbum.colors
<https://plumbum.readthedocs.io/en/latest/colors.html>`_, `colored
<https://gitlab.com/dslackw/colored>`_, or `colorama
<https://github.com/tartley/colorama>`_. Colorama is unique because when it's
running on Windows, it wraps ``stdout``, looks for ANSI escape sequences, and
converts them into the appropriate ``win32`` calls to modify the state of the
terminal.

``cmd2`` imports and uses Colorama and also provides a number of convenience
methods for generating colorized output, measuring the screen width of
colorized output, setting the window title in the terminal, and removing ANSI
escape codes from a string. These functions are all documentated in
:ref:`api/ansi:cmd2.ansi`.


Error Messages
--------------


Warning Messages
----------------


Feedback
--------

You may have the need to display information to the user which is not intended
to be part of the generated output. This could be debugging information or
status information about the progress of long running commands. It's not
output, it's not error messages, it's feedback. If you use the
:ref:`features/settings:Timing` setting, the output of how long it took the
command to run will be output as feedback. ``cmd2`` has a ``self.pfeedback()``
method to produce this type of output, and several
:ref:`features/settings:Settings` to control how this output is handled.

If the ``quiet`` setting is ``True``, then calling ``self.pfeedback()``
produces no output. If ``quiet`` is ``False``, then the ``feedback_to_output``
setting is consulted to determine which file descriptor the feedback will be
sent to. The default value of ``False`` means all feedback is sent to
``sys.stderr``. If set to ``True``, then the feedback output will be sent to
``self.stdout`` along with the rest of the generated output.


Exceptions
----------


Paging Output
-------------


Centering Text
--------------

utils.center_text()


Columnar Output
---------------

Using wcswidth() and ansi.ansi_safe_wcswidth()



