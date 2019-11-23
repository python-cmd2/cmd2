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
:ref:`features/redirection:Output Redirection And Pipes` for information
on how users can change where the output of a command is sent. In order
for those features to work, the output you generate must be sent to
``self.stdout``. You can use the methods described above, and everything
will work fine. ``cmd2`` also includes a number of convenience methods
which you may use to enhance the output your application produces.


TODO:

- poutput
- perror
- pwarning
- pexcept
- ppaging

- column formatting?
- wcswidth?

- allow_ansi setting
- cmd2.ansi.style()

- exceptions

Ordinary Output
---------------


Error Messages
--------------


Warning Messages
----------------


Feedback
--------

You may have the need to display information to the user which is not intended
to be part of the generated output. This could be debugging information or
status information about the progress of long running commands. It's not output,
it's not error messages, it's feedback. If you use the
:ref:`features/settings:Timing` setting, the output of how long it took the
command to run will be output as feedback. ``cmd2`` has a ``self.pfeedback()``
method to produce this type of output, and several
:ref:`features/settings:Settings` to control how this output is handled.

If the ``quiet`` setting is ``True``, then calling ``self.pfeedback()`` produces
no output. If ``quiet`` is ``False``, then the ``feedback_to_output`` setting is
consulted to determine which file descriptor the feedback will be sent to. The
default value of ``False`` means all feedback is sent to ``sys.stderr``. If set
to ``True``, then the feedback output will be sent to ``self.stdout`` along with
the rest of the generated output.


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


Colored Output
--------------

The output methods in the previous section all honor the ``allow_ansi``
setting, which has three possible values:

Never
    poutput(), pfeedback(), and ppaged() strip all ANSI escape sequences
    which instruct the terminal to colorize output

Terminal
    (the default value) poutput(), pfeedback(), and ppaged() do not strip any
    ANSI escape sequences when the output is a terminal, but if the output is a
    pipe or a file the escape sequences are stripped. If you want colorized
    output you must add ANSI escape sequences using either cmd2's internal ansi
    module or another color library such as `plumbum.colors`, `colorama`, or
    `colored`.

Always
    poutput(), pfeedback(), and ppaged() never strip ANSI escape sequences,
    regardless of the output destination

Colored and otherwise styled output can be generated using the `ansi.style()`
function:

.. automethod:: cmd2.ansi.style

