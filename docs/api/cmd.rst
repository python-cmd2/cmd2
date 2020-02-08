cmd2.Cmd
========

.. autoclass:: cmd2.Cmd
    :members:

    .. automethod:: __init__

    .. attribute:: continuation_prompt

      Use as prompt for multiline commands on the 2nd+ line of input.
      Default: ``>``.

    .. attribute:: default_error

      The error message displayed when a non-existent command is run.
      Default: ``{} is not a recognized command, alias, or macro``

    .. attribute:: help_error

      The error message displayed to the user when they request help for a
      command with no help defined.
      Default:  ``No help on {}``

    .. attribute:: prompt

      The prompt issued to solicit input.
      Default: ``(Cmd)``.

    .. attribute:: settable

        This dictionary contains the name and description of all settings available to users.

        Users use the :ref:`features/builtin_commands:set` command to view and
        modify settings. Settings are stored in instance attributes with the
        same name as the setting.
