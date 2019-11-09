Generating Output
=================

how to generate output

- poutput
- perror
- paging
- exceptions
- color support

Standard ``cmd`` applications produce their output with
``self.stdout.write('output')`` (or with ``print``, but ``print`` decreases
output flexibility).  ``cmd2`` applications can use ``self.poutput('output')``,
``self.pfeedback('message')``, ``self.perror('errmsg')``, and
``self.ppaged('text')`` instead.  These methods have these advantages:

- Handle output redirection to file and/or pipe appropriately
- More concise
    - ``.pfeedback()`` destination is controlled by ``quiet`` parameter.
- Option to display long output using a pager via ``ppaged()``

.. automethod:: cmd2.cmd2.Cmd.poutput
    :noindex:
.. automethod:: cmd2.cmd2.Cmd.perror
    :noindex:
.. automethod:: cmd2.cmd2.Cmd.pfeedback
    :noindex:
.. automethod:: cmd2.cmd2.Cmd.ppaged
    :noindex:


Suppressing non-essential output
--------------------------------

The ``quiet`` setting controls whether ``self.pfeedback()`` actually produces
any output. If ``quiet`` is ``False``, then the output will be produced. If
``quiet`` is ``True``, no output will be produced.

This makes ``self.pfeedback()`` useful for non-essential output like status
messages. Users can control whether they would like to see these messages by
changing the value of the ``quiet`` setting.


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

