Builtin Commands
================

Applications which subclass :class:`cmd2.cmd2.Cmd` inherit a number of commands
which may be useful to your users.

edit
----

This command launches an editor program and instructs it to open the given file
name. Here's an example::

  (Cmd) edit ~/.ssh/config

The program to be launched is determined by the value of the
:ref:`features/settings:editor` setting.


set
---

A list of all user-settable parameters, with brief comments, is viewable from
within a running application::

    (Cmd) set --long
    allow_style: Terminal          # Allow ANSI escape sequences in output (valid values: Terminal, Always, Never)
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
the ``set`` command like so::

    (Cmd) set allow_style Never


Removing A Builtin Command
--------------------------

[TODO] show how to remove a builtin command if you don't want it available to
your users.
