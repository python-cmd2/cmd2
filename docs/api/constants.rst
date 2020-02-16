cmd2.constants
==============

.. automodule:: cmd2.constants

  .. data:: DEFAULT_SHORTCUTS

    If you do not supply shortcuts to :meth:`cmd2.Cmd.__init__`, the shortcuts
    defined here will be used instead.


  .. data:: COMMAND_NAME

    Used by :meth:`cmd2.Cmd.disable_command` and
    :meth:`cmd2.Cmd.disable_category`. Those methods allow you to selectively
    disable single commands or an entire category of commands. Should you want
    to include the name of the command in the error message displayed to the
    user when they try and run a disabled command, you can include this
    constant in the message where you would like the name of the command to
    appear. ``cmd2`` will replace this constant with the name of the command
    the user tried to run before displaying the error message.

    This constant is imported into the package namespace; the preferred syntax
    to import and reference it is::

        import cmd2
        errmsg = "The {} command is currently disabled.".format(cmd2.COMMAND_NAME)

    See ``src/examples/help_categories.py`` for an example.
