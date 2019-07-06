Prompt
======

``cmd2`` can issue a prompt before soliciting user input.

Asynchronous Feedback
---------------------

``cmd2`` provides two functions to provide asynchronous feedback to the user
without interfering with the command line. This means the feedback is provided
to the user when they are still entering text at the prompt. To use this
functionality, the application must be running in a terminal that supports
VT100 control characters and readline. Linux, Mac, and Windows 10 and greater
all support these.

async_alert()
    Used to display an important message to the user while they are at the
    prompt in between commands. To the user it appears as if an alert message
    is printed above the prompt and their current input text and cursor
    location is left alone.

async_update_prompt()
    Updates the prompt while the user is still typing at it. This is good for
    alerting the user to system changes dynamically in between commands. For
    instance you could alter the color of the prompt to indicate a system
    status or increase a counter to report an event.

``cmd2`` also provides a function to change the title of the terminal window.
This feature requires the application be running in a terminal that supports
VT100 control characters. Linux, Mac, and Windows 10 and greater all support
these.

set_window_title()
    Sets the terminal window title


The easiest way to understand these functions is to see the AsyncPrinting_
example for a demonstration.

.. _AsyncPrinting: https://github.com/python-cmd2/cmd2/blob/master/examples/async_printing.py


