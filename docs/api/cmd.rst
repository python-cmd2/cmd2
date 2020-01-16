cmd2.Cmd
========

.. autoclass:: cmd2.cmd2.Cmd
    :members:

    .. attribute:: help_error

      The error message displayed to the user when they request help for a
      command with no help defined.

    .. attribute:: default_error

      The error message displayed when a non-existent command is run.

    .. attribute:: settable

        This dictionary contains the name and description of all settings available to users.

        Users use the :ref:`features/builtin_commands:set` command to view and
        modify settings. Settings are stored in instance attributes with the
        same name as the setting.
