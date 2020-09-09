cmd2.Cmd
========

.. autoclass:: cmd2.Cmd
    :members:

    .. automethod:: __init__

    .. attribute:: default_error

      The error message displayed when a non-existent command is run.
      Default: ``{} is not a recognized command, alias, or macro``

    .. attribute:: help_error

      The error message displayed to the user when they request help for a
      command with no help defined.
      Default:  ``No help on {}``

    .. attribute:: prompt

      The prompt issued to solicit input. The default value is ``(Cmd)``.
      See :ref:`features/prompt:Prompt` for more information.

    .. attribute:: continuation_prompt

      The prompt issued to solicit input for the 2nd and subsequent lines
      of a :ref:`multiline command <features/multiline_commands:Multiline Commands>`
      Default: ``>``.

    .. attribute:: echo

      If ``True``, output the prompt and user input before executing the command.
      When redirecting a series of commands to an output file, this allows you to
      see the command in the output.

    .. attribute:: settable

        This dictionary contains the name and description of all settings
        available to users.

        Users use the :ref:`features/builtin_commands:set` command to view and
        modify settings. Settings are stored in instance attributes with the
        same name as the setting.

    .. attribute:: history

        A record of previously entered commands.

        This attribute is an instance of :class:`cmd2.history.History`, and
        each command is an instance of :class:`cmd2.Statement`.

    .. attribute:: statement_parser

        An instance of :class:`cmd2.parsing.StatementParser` initialized and
        configured appropriately for parsing user input.

    .. attribute:: intro

        Set an introduction message which is displayed to the user before
        the :ref:`features/hooks:Command Processing Loop` begins.

    .. attribute:: py_bridge_name

        The symbol name which :ref:`features/scripting:Python Scripts` run
        using the :ref:`features/builtin_commands:run_pyscript` command can use
        to reference the parent ``cmd2`` application.
