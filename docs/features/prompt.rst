Prompt
======

``cmd2`` issues a configurable prompt before soliciting user input.

Customizing the Prompt
----------------------

This prompt can be configured by setting the :attr:`cmd2.Cmd.prompt` instance
attribute. This contains the string which should be printed as a prompt
for user input.  See the Pirate_ example for the simple use case of statically
setting the prompt.

.. _Pirate: https://github.com/python-cmd2/cmd2/blob/master/examples/pirate.py#L33

Continuation Prompt
-------------------

When a user types a
:ref:`Multiline Command <features/multiline_commands:Multiline Commands>`
it may span more than one line of input. The prompt for the first line of input
is specified by the :attr:`cmd2.Cmd.prompt` instance attribute.  The prompt for
subsequent lines of input is defined by the
:attr:`cmd2.Cmd.continuation_prompt` attribute.See the Initialization_ example
for a demonstration of customizing the continuation prompt.

.. _Initialization: https://github.com/python-cmd2/cmd2/blob/master/examples/initialization.py#L33

Updating the prompt
-------------------

If you wish to update the prompt between commands, you can do so using one of
the :ref:`Application Lifecycle Hooks <features/hooks:Hooks>` such as a
:ref:`Postcommand hook <features/hooks:Postcommand Hooks>`.  See
PythonScripting_ for an example of dynamically updating the prompt.

.. _PythonScripting: https://github.com/python-cmd2/cmd2/blob/master/examples/python_scripting.py#L34-L48

Asynchronous Feedback
---------------------

``cmd2`` provides two functions to provide asynchronous feedback to the user
without interfering with the command line. This means the feedback is provided
to the user when they are still entering text at the prompt. To use this
functionality, the application must be running in a terminal that supports
VT100 control characters and readline. Linux, Mac, and Windows 10 and greater
all support these.

.. automethod:: cmd2.Cmd.async_alert
    :noindex:

.. automethod:: cmd2.Cmd.async_update_prompt
    :noindex:

``cmd2`` also provides a function to change the title of the terminal window.
This feature requires the application be running in a terminal that supports
VT100 control characters. Linux, Mac, and Windows 10 and greater all support
these.

.. automethod:: cmd2.Cmd.set_window_title
    :noindex:

The easiest way to understand these functions is to see the AsyncPrinting_
example for a demonstration.

.. _AsyncPrinting: https://github.com/python-cmd2/cmd2/blob/master/examples/async_printing.py


