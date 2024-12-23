# cmd2.Cmd

TODO replace with mkdocstrings:

    > :::::::::::::::: {.autoclass members=""}
    > cmd2.Cmd
    >
    > ::: automethod
    > :::
    >
    > ::: attribute
    > default[error]{#error}
    >
    > The error message displayed when a non-existent command is run. Default: `{} is not a recognized command, alias, or macro.`
    > :::
    >
    > ::: attribute
    > help[error]{#error}
    >
    > The error message displayed to the user when they request help for a command with no help defined. Default: `No help on {}`
    > :::
    >
    > ::: attribute
    > prompt
    >
    > The prompt issued to solicit input. The default value is `(Cmd)`. See `features/prompt:Prompt`{.interpreted-text role="ref"} for more information.
    > :::
    >
    > ::: attribute
    > continuation[prompt]{#prompt}
    >
    > The prompt issued to solicit input for the 2nd and subsequent lines of a `multiline command <features/multiline_commands:Multiline Commands>`{.interpreted-text role="ref"} Default: `>`.
    > :::
    >
    > ::: attribute
    > echo
    >
    > If `True`, output the prompt and user input before executing the command. When redirecting a series of commands to an output file, this allows you to see the command in the output.
    > :::
    >
    > ::: attribute
    > settable
    >
    > This dictionary contains the name and description of all settings available to users.
    >
    > Users use the `features/builtin_commands:set`{.interpreted-text role="ref"} command to view and modify settings. Settings are stored in instance attributes with the same name as the setting.
    > :::
    >
    > ::: attribute
    > history
    >
    > A record of previously entered commands.
    >
    > This attribute is an instance of `cmd2.history.History`{.interpreted-text role="class"}, and each command is an instance of `cmd2.Statement`{.interpreted-text role="class"}.
    > :::
    >
    > ::: attribute
    > statement[parser]{#parser}
    >
    > An instance of `cmd2.parsing.StatementParser`{.interpreted-text role="class"} initialized and configured appropriately for parsing user input.
    > :::
    >
    > ::: attribute
    > intro
    >
    > Set an introduction message which is displayed to the user before the `features/hooks:Command Processing Loop`{.interpreted-text role="ref"} begins.
    > :::
    >
    > ::: attribute
    > py[bridge_name]{#bridge_name}
    >
    > The symbol name which `features/scripting:Python Scripts`{.interpreted-text role="ref"} run using the `features/builtin_commands:run_pyscript`{.interpreted-text role="ref"} command can use to reference the parent `cmd2` application.
    > :::
    >
    > ::: attribute
    > allow[clipboard]{#clipboard}
    >
    > If `True`, `cmd2` will allow output to be written to or appended to the operating system pasteboard. If `False`, this capability will not be allowed. See `features/clipboard:Clipboard Integration`{.interpreted-text role="ref"} for more information.
    > :::
    >
    > ::: attribute
    > suggest[similar_command]{#similar_command}
    >
    > If `True`, `cmd2` will attempt to suggest the most similar command when the user types a command that does not exist. Default: `False`.
    > :::
    > ::::::::::::::::
