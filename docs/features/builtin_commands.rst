Builtin Commands
================

Applications which subclass :class:`cmd2.cmd2.Cmd` inherit a number of commands
which may be useful to your users. Developers can
:ref:`features/builtin_commands:Remove Builtin Commands` if they do not want
them to be part of the application.

edit
----

This command launches an editor program and instructs it to open the given file
name. Here's an example:

.. code-block:: text

  (Cmd) edit ~/.ssh/config

The program to be launched is determined by the value of the
:ref:`features/settings:editor` setting.


set
---

A list of all user-settable parameters, with brief comments, is viewable from
within a running application:

.. code-block:: text

    (Cmd) set --long
    allow_style: Terminal          # Allow ANSI text style sequences in output (valid values: Terminal, Always, Never)
    continuation_prompt: >         # On 2nd+ line of input
    debug: False                   # Show full error stack on error
    echo: False                    # Echo command issued into output
    editor: vim                    # Program used by ``edit``
    feedback_to_output: False      # include nonessentials in `|`, `>` results
    locals_in_py: False            # Allow access to your application in py via self
    max_completion_items: 50       # Maximum number of CompletionItems to display during tab completion
    prompt: (Cmd)                  # The prompt issued to solicit input
    quiet: False                   # Don't print nonessential feedback
    timing: False                  # Report execution times

Any of these user-settable parameters can be set while running your app with
the ``set`` command like so:

.. code-block:: text

    (Cmd) set allow_style Never


shell
-----

Execute a command as if at the operating system shell prompt:

.. code-block:: text

    (Cmd) shell pwd -P
    /usr/local/bin


Remove Builtin Commands
-----------------------

Developers may not want to offer the commands builtin to :class:`cmd2.cmd2.Cmd`
to users of their application. To remove a command you must delete the method
implementing that command from the :class:`cmd2.cmd2.Cmd` object at runtime.
For example, if you wanted to remove the :ref:`features/builtin_commands:shell`
command from your application::

    class NoShellApp(cmd2.Cmd):
        """A simple cmd2 application."""

        delattr(cmd2.Cmd, 'do_shell')
