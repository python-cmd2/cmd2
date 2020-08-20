Scripting
=========

Operating system shells have long had the ability to execute a sequence of
commands saved in a text file. These script files make long sequences of
commands easier to repeatedly execute. ``cmd2`` supports two similar
mechanisms: command scripts and python scripts.


Command Scripts
---------------

A command script contains a sequence of commands typed at the the prompt of a
``cmd2`` based application. Unlike operating system shell scripts, command
scripts can't contain logic or loops.


Creating Command Scripts
~~~~~~~~~~~~~~~~~~~~~~~~

Command scripts can be created in several ways:

- creating a text file using any method of your choice
- using the built-in :ref:`features/builtin_commands:edit` command to
  create or edit an existing text file
- saving previously entered commands to a script file using
  :ref:`history -s <features/history:For Users>`

If you create create a text file from scratch, just include one command per
line, exactly as you would type it inside a ``cmd2`` application.


Running Command Scripts
~~~~~~~~~~~~~~~~~~~~~~~

Command script files can be executed using the built-in
:ref:`features/builtin_commands:run_script` command or the ``@`` shortcut (if
your application is using the default shortcuts). Both ASCII and UTF-8 encoded
unicode text files are supported. The
:ref:`features/builtin_commands:run_script` command supports tab completion of
file system paths.  There is a variant
:ref:`features/builtin_commands:_relative_run_script` command or ``@@``
shortcut (if using the default shortcuts) for use within a script which uses
paths relative to the first script.


Comments
~~~~~~~~

Any command line input where the first non-whitespace character is a `#` will
be treated as a comment. This means any `#` character appearing later in the
command will be treated as a literal. The same applies to a `#` in the middle
of a multiline command, even if it is the first character on a line.

Comments are useful in scripts, but would be pointless within an interactive
session.

::

  (Cmd) # this is a comment
  (Cmd) command # this is not a comment


.. _scripting-python-scripts:

Python Scripts
--------------

.. _arg_printer:
   https://github.com/python-cmd2/cmd2/blob/master/examples/scripts/arg_printer.py

If you require logic flow, loops, branching, or other advanced features, you
can write a python script which executes in the context of your ``cmd2`` app.
This script is run using the :ref:`features/builtin_commands:run_pyscript`
command. Here's a simple example that uses the arg_printer_ script::

    (Cmd) run_pyscript examples/scripts/arg_printer.py foo bar 'baz 23'
    Running Python script 'arg_printer.py' which was called with 3 arguments
    arg 1: 'foo'
    arg 2: 'bar'
    arg 3: 'baz 23'

:ref:`features/builtin_commands:run_pyscript` supports tab completion of file
system paths, and as shown above it has the ability to pass command-line
arguments to the scripts invoked.

Python scripts executed with :ref:`features/builtin_commands:run_pyscript` can
run ``cmd2`` application commands by using the syntax::

    app(‘command args’)

where:

* ``app`` is a configurable name which can be changed by setting the
  :data:`cmd2.Cmd.py_bridge_name` attribute
* ``command`` and ``args`` are entered exactly like they would be entered by
  a user of your application.

See python_scripting_ example and associated conditional_ script for more
information.

Advanced Support
~~~~~~~~~~~~~~~~

When implementing a command, setting ``self.last_result`` allows for application-specific
data to be returned to a python script from the command. This can allow python scripts to
make decisions based on the result of previous application commands.

The application command (default: ``app``) returns a ``cmd2.CommandResult`` for each command.
The ``cmd2.CommandResult`` object provides the captured output to ``stdout`` and ``stderr``
while a command is executing. Additionally, it provides the value that command stored in
``self.last_result``.

Additionally, an external test Mixin plugin has been provided to allow for python based
external testing of the application. For example, for system integration tests scenarios
where the python application is a component of a larger suite of tools and components. This
interface allows python based tests to call commands and validate results as part of a
larger test suite. See :ref:`plugins/external_test:External Test Plugin`

.. _python_scripting:
   https://github.com/python-cmd2/cmd2/blob/master/examples/python_scripting.py

.. _conditional:
   https://github.com/python-cmd2/cmd2/blob/master/examples/scripts/conditional.py
