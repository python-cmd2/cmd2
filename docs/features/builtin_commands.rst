Builtin Commands
================

Applications which subclass :class:`cmd2.Cmd` inherit a number of commands
which may be useful to your users. Developers can
:ref:`features/builtin_commands:Remove Builtin Commands` if they do not want
them to be part of the application.

List of Builtin Commands
------------------------

alias
~~~~~

This command manages aliases via subcommands ``create``, ``delete``, and
``list``.  See :ref:`features/shortcuts_aliases_macros:Aliases` for more
information.

edit
~~~~

This command launches an editor program and instructs it to open the given file
name. Here's an example:

.. code-block:: text

  (Cmd) edit ~/.ssh/config

The program to be launched is determined by the value of the
:ref:`features/settings:editor` setting.

help
~~~~

This command lists available commands or provides detailed help for a specific
command. When called with the ``-v/--verbose`` argument, it shows a brief
description of each command.  See :ref:`features/help:Help` for more
information.

history
~~~~~~~

This command allows you to view, run, edit, save, or clear previously entered
commands from the history.  See :ref:`features/history:History` for more
information.

ipy
~~~

This optional opt-in command enters an interactive IPython shell.  See
:ref:`features/embedded_python_shells:IPython (optional)` for more information.

macro
~~~~~

This command manages macros via subcommands ``create``, ``delete``, and
``list``.  A macro is similar to an alias, but it can contain argument
placeholders.  See :ref:`features/shortcuts_aliases_macros:Macros` for more
information.

py
~~

This command invokes a Python command or shell.  See
:ref:`features/embedded_python_shells:Embedded Python Shells` for more
information.

quit
~~~~

This command exits the ``cmd2`` application.

run_pyscript
~~~~~~~~~~~~

This command runs a Python script file inside the ``cmd2`` application.
See :ref:`features/scripting:Python Scripts` for more information.

run_script
~~~~~~~~~~

This command runs commands in a script file that is encoded as either ASCII
or UTF-8 text.  See :ref:`features/scripting:Command Scripts` for more
information.

_relative_run_script
~~~~~~~~~~~~~~~~~~~~

This command is hidden from the help that's visible to end users. It runs a
script like :ref:`features/builtin_commands:run_script` but does so using a
path relative to the script that is currently executing. This is useful when
you have scripts that run other scripts. See :ref:`features/scripting:Running
Command Scripts` for more information.

set
~~~

A list of all user-settable parameters, with brief comments, is viewable from
within a running application:

.. code-block:: text

    (Cmd) set --long
    allow_style: Terminal          # Allow ANSI text style sequences in output (valid values: Terminal, Always, Never)
    debug: False                   # Show full traceback on exception
    echo: False                    # Echo command issued into output
    editor: vim                    # Program used by 'edit'
    feedback_to_output: False      # include nonessentials in '|', '>' results
    max_completion_items: 50       # Maximum number of CompletionItems to display during tab completion
    quiet: False                   # Don't print nonessential feedback
    timing: False                  # Report execution times

Any of these user-settable parameters can be set while running your app with
the ``set`` command like so:

.. code-block:: text

    (Cmd) set allow_style Never

See :ref:`features/settings:Settings` for more information.

shell
~~~~~

Execute a command as if at the operating system shell prompt:

.. code-block:: text

    (Cmd) shell pwd -P
    /usr/local/bin

shortcuts
~~~~~~~~~

This command lists available shortcuts.  See
:ref:`features/shortcuts_aliases_macros:Shortcuts` for more information.


Remove Builtin Commands
-----------------------

Developers may not want to offer the commands builtin to :class:`cmd2.Cmd`
to users of their application. To remove a command you must delete the method
implementing that command from the :class:`cmd2.Cmd` object at runtime.
For example, if you wanted to remove the :ref:`features/builtin_commands:shell`
command from your application::

    class NoShellApp(cmd2.Cmd):
        """A simple cmd2 application."""

        delattr(cmd2.Cmd, 'do_shell')
