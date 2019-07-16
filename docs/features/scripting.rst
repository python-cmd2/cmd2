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
- using the built-in ``edit`` command to create or edit an existing text file
- saving previously entered commands to a script file using ``history -s``. See
  :ref:`features/history:History` for more details.

If you create create a text file from scratch, just include one command per
line, exactly as you would type it inside a ``cmd2`` application.


Running Command Scripts
~~~~~~~~~~~~~~~~~~~~~~~

Command script files can be executed using the built-in ``run_script`` command.
Both ASCII and UTF-8 encoded unicode text files are supported.


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


Python Scripts
--------------

If you require logic flow, loops, branching, or other advanced features, you
can write a python script which executes in the context of your ``cmd2`` app.
This script is run using the ``run_pyscript`` command. See
:ref:`features/embedded_python_shells:Embedded Python Shells`.
