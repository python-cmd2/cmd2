Completion
==========

``cmd2`` adds tab-completion of file system paths for all built-in commands
where it makes sense, including:

- ``edit``
- ``run_pyscript``
- ``run_script``
- ``shell``

``cmd2`` also adds tab-completion of shell commands to the ``shell`` command.

Additionally, it is trivial to add identical file system path completion to
your own custom commands.  Suppose you have defined a custom command ``foo`` by
implementing the ``do_foo`` method.  To enable path completion for the ``foo``
command, then add a line of code similar to the following to your class which
inherits from ``cmd2.Cmd``::

    complete_foo = self.path_complete

This will effectively define the ``complete_foo`` readline completer method in
your class and make it utilize the same path completion logic as the built-in
commands.

The built-in logic allows for a few more advanced path completion capabilities,
such as cases where you only want to match directories.  Suppose you have a
custom command ``bar`` implemented by the ``do_bar`` method.  You can enable
path completion of directories only for this command by adding a line of code
similar to the following to your class which inherits from ``cmd2.Cmd``::

    # Make sure you have an "import functools" somewhere at the top
    complete_bar = functools.partialmethod(cmd2.Cmd.path_complete, path_filter=os.path.isdir)
