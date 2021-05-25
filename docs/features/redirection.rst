Output Redirection and Pipes
============================

As in POSIX shells, output of a command can be redirected and/or piped.  This
feature is fully cross-platform and works identically on Windows, macOS, and
Linux.

Output Redirection
------------------

Redirect to a file
~~~~~~~~~~~~~~~~~~

Redirecting the output of a ``cmd2`` command to a file works just like in
POSIX shells:

  - send to a file with ``>``, as in ``mycommand args > filename.txt``
  - append to a file with ``>>``, as in ``mycommand args >> filename.txt``

If you need to include any of these redirection characters in your command, you
can enclose them in quotation marks, ``mycommand 'with > in the argument'``.

Redirect to the clipboard
~~~~~~~~~~~~~~~~~~~~~~~~~

``cmd2`` output redirection supports an additional feature not found in most
shells - if the file name following the ``>`` or ``>>`` is left blank, then
the output is redirected to the operating system clipboard so that it can
then be pasted into another program.

  - overwrite the clipboard with ``mycommand args >``
  - append to the clipboard with ``mycommand args >>``

Pipes
-----
Piping the output of a ``cmd2`` command to a shell command works just like in
POSIX shells:

  - pipe as input to a shell command with ``|``, as in ``mycommand args | wc``

Multiple Pipes and Redirection
------------------------------
Multiple pipes, optionally followed by a redirect, are supported.  Thus, it is
possible to do something like the following::

    (Cmd) help | grep py | wc > output.txt

The above runs the **help** command, pipes its output to **grep** searching for
any lines containing *py*, then pipes the output of grep to the **wc**
"word count" command, and finally writes redirects the output of that to a file
called *output.txt*.

Disabling Redirection
---------------------

.. note::

   If you wish to disable cmd2's output redirection and pipes features, you can
   do so by setting the ``allow_redirection`` attribute of your ``cmd2.Cmd``
   class instance to ``False``.  This would be useful, for example, if you want
   to restrict the ability for an end user to write to disk or interact with
   shell commands for security reasons::

       from cmd2 import Cmd
       class App(Cmd):
           def __init__(self):
               super().__init__(allow_redirection=False)

   cmd2's parser will still treat the ``>``, ``>>``, and `|` symbols as output
   redirection and pipe symbols and will strip arguments after them from the
   command line arguments accordingly.  But output from a command will not be
   redirected to a file or piped to a shell command.

Limitations of Redirection
--------------------------

Some limitations apply to redirection and piping within ``cmd2`` applications:

- Can only pipe to shell commands, not other ``cmd2`` application commands
- **stdout** gets redirected/piped, **stderr** does not
