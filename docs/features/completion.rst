Completion
==========

:class:`cmd2.Cmd` adds tab completion of file system paths for all built-in
commands where it makes sense, including:

- :ref:`features/builtin_commands:edit`
- :ref:`features/builtin_commands:run_pyscript`
- :ref:`features/builtin_commands:run_script`
- :ref:`features/builtin_commands:shell`

:class:`cmd2.Cmd` also adds tab completion of shell commands to the
:ref:`features/builtin_commands:shell` command.

It is easy to add identical file system path completion to your own custom
commands.  Suppose you have defined a custom command ``foo`` by implementing
the ``do_foo`` method.  To enable path completion for the ``foo`` command, then
add a line of code similar to the following to your class which inherits from
:class:`cmd2.Cmd`::

    complete_foo = cmd2.Cmd.path_complete

This will effectively define the ``complete_foo`` readline completer method in
your class and make it utilize the same path completion logic as the built-in
commands.

The built-in logic allows for a few more advanced path completion capabilities,
such as cases where you only want to match directories.  Suppose you have a
custom command ``bar`` implemented by the ``do_bar`` method.  You can enable
path completion of directories only for this command by adding a line of code
similar to the following to your class which inherits from :class:`cmd2.Cmd`::

    # Make sure you have an "import functools" somewhere at the top
    complete_bar = functools.partialmethod(cmd2.Cmd.path_complete, path_filter=os.path.isdir)


Included Tab Completion Functions
---------------------------------
``cmd2`` provides the following tab completion functions

- :attr:`cmd2.Cmd.basic_complete` - helper method for tab completion against
  a list
- :attr:`cmd2.Cmd.path_complete` - helper method provides flexible tab
  completion of file system paths

        - See the paged_output_ example for a simple use case
        - See the python_scripting_ example for a more full-featured use case

- :attr:`cmd2.Cmd.delimiter_complete` - helper method for tab completion
  against a list but each match is split on a delimiter

        - See the basic_completion_ example for a demonstration of how to use
          this feature

- :attr:`cmd2.Cmd.flag_based_complete` - helper method for tab completion based
  on a particular flag preceding the token being completed
- :attr:`cmd2.Cmd.index_based_complete` - helper method for tab completion
  based on a fixed position in the input string

    - See the basic_completion_ example for a demonstration of how to use these
      features
    - ``flag_based_complete()`` and ``index_based_complete()`` are basic
      methods and should only be used if you are not familiar with argparse.
      The recommended approach for tab completing positional tokens and flags
      is to use argparse-based_ completion.

.. _paged_output: https://github.com/python-cmd2/cmd2/blob/master/examples/paged_output.py
.. _python_scripting: https://github.com/python-cmd2/cmd2/blob/master/examples/python_scripting.py
.. _basic_completion: https://github.com/python-cmd2/cmd2/blob/master/examples/basic_completion.py


Raising Exceptions During Completion
------------------------------------
There are times when an error occurs while tab completing and a message needs
to be reported to the user. These include the following example cases:

- Reading a database to retrieve a tab completion data set failed
- A previous command line argument that determines the data set being completed
  is invalid
- Tab completion hints

``cmd2`` provides the :class:`cmd2.exceptions.CompletionError` exception class for
this capability. If an error occurs in which it is more desirable to display
a message than a stack trace, then raise a ``CompletionError``. By default, the
message displays in red like an error. However, ``CompletionError`` has a
member called ``apply_style``. Set this False if the error style should not be
applied. For instance, ``ArgparseCompleter`` sets it to False when displaying
completion hints.

.. _argparse-based:


Tab Completion Using argparse Decorators
----------------------------------------

When using one the argparse-based :ref:`api/decorators:cmd2.decorators`,
``cmd2`` provides automatic tab completion of flag names.

Tab completion of argument values can be configured by using one of three
parameters to :meth:`argparse.ArgumentParser.add_argument`

- ``choices``
- ``choices_provider``
- ``completer``

See the arg_decorators_ or colors_ example for a demonstration of how to
use the ``choices`` parameter. See the argparse_completion_ example for a
demonstration of how to use the ``choices_provider`` parameter. See the
arg_decorators_ or argparse_completion_ example for a demonstration
of how to use the ``completer`` parameter.

When tab completing flags or argument values for a ``cmd2`` command using
one of these decorators, ``cmd2`` keeps track of state so that once a flag has
already previously been provided, it won't attempt to tab complete it again.
When no completion results exists, a hint for the current argument will be
displayed to help the user.

.. _arg_decorators: https://github.com/python-cmd2/cmd2/blob/master/examples/arg_decorators.py
.. _colors: https://github.com/python-cmd2/cmd2/blob/master/examples/colors.py
.. _argparse_completion: https://github.com/python-cmd2/cmd2/blob/master/examples/argparse_completion.py


CompletionItem For Providing Extra Context
------------------------------------------

When tab completing things like a unique ID from a database, it can often be
beneficial to provide the user with some extra context about the item being
completed, such as a description.  To facilitate this, ``cmd2`` defines the
:class:`cmd2.argparse_custom.CompletionItem` class which can be returned from
any of the 3 completion parameters: ``choices``, ``choices_provider``, and
``completer``.

See the argparse_completion_ example or the implementation of the built-in
:meth:`~cmd2.Cmd.do_set` command for demonstration of how this is used.


Custom Completion with ``read_input()``
--------------------------------------------------

``cmd2`` provides :attr:`cmd2.Cmd.read_input` as an alternative to Python's
``input()`` function. ``read_input`` supports configurable tab completion and
up-arrow history at the prompt. See read_input_ example for a demonstration.

.. _read_input: https://github.com/python-cmd2/cmd2/blob/master/examples/read_input.py


For More Information
--------------------

See :mod:`cmd2.argparse_custom` for a more detailed discussion of argparse
completion.
