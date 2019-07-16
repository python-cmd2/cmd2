Clipboard Integration
=====================

Nearly every operating system has some notion of a short-term storage area
which can be accessed by any program. Usually this is called the clipboard, but
sometimes people refer to it as the paste buffer.

``cmd2`` integrates with the operating system clipboard using the `pyperclip
<https://github.com/asweigart/pyperclip>`_ module. Command output can be sent
to the clipboard by ending the command with a greater than symbol:

.. code-block:: text

    mycommand args >

Think of it as though you are redirecting output to an unnamed, ephemeral
place, you know, like the clipboard. You can also append output to the current
contents of the clipboard by ending the command with two greater than symbols:

.. code-block:: text

    mycommand arg1 arg2 >>


Developers
----------

If you would like your ``cmd2`` based application to be able to use the
clipboard in additional or alternative ways, you can use the following methods
(which work uniformly on Windows, macOS, and Linux).

.. automodule:: cmd2.clipboard
    :members:
