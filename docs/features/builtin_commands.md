# Builtin Commands

Applications which subclass [cmd2.Cmd][] inherit a number of commands which may be useful to your
users. Developers can [Remove Builtin Commands](#remove-builtin-commands) if they do not want them
to be part of the application.

## List of Builtin Commands

### alias

This command manages aliases via subcommands `create`, `delete`, and `list`. See
[Aliases](shortcuts_aliases_macros.md#aliases) for more information.

### edit

This command launches an editor program and instructs it to open the given file name. Here's an
example:

```sh
(Cmd) edit ~/.ssh/config
```

The program to be launched is determined by the value of the [editor](settings.md#editor) setting.

### help

This command lists available commands or provides detailed help for a specific command. When called
with the `-v/--verbose` argument, it shows a brief description of each command. See [Help](help.md)
for more information.

### history

This command allows you to view, run, edit, save, or clear previously entered commands from the
history. See [History](history.md) for more information.

### ipy (optional)

This optional opt-in command enters an interactive :simple-jupyter: IPython shell. See
[IPython (optional)](./embedded_python_shells.md#ipython-optional) for more information.

### macro

This command manages macros via subcommands `create`, `delete`, and `list`. A macro is similar to an
alias, but it can contain argument placeholders. See [Macros](./shortcuts_aliases_macros.md#macros)
for more information.

### py (optional)

This optional opt-in command invokes a Python command or shell. See
[Embedded Python Shells](./embedded_python_shells.md) for more information.

### quit

This command exits the `cmd2` application.

### run_pyscript

This command runs a Python script file inside the `cmd2` application. See
[Python Scripts](./scripting.md#python-scripts) for more information.

### run_script

This command runs commands in a script file that is encoded as either ASCII or UTF-8 text. See
[Command Scripts](./scripting.md#command-scripts) for more information.

### \_relative_run_script

**This command is hidden from the help that's visible to end users.** It runs a script like
[run_script](#run_script) but does so using a path relative to the script that is currently
executing. This is useful when you have scripts that run other scripts. See
[Running Command Scripts](../features/scripting.md#running-command-scripts) for more information.

### set

A list of all user-settable parameters, with brief comments, is viewable from within a running
application:

```text
(Cmd) set
 Name                     Value      Description
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 allow_style              Terminal   Allow ANSI text style sequences in output (valid values: Always, Never, Terminal)
 always_show_hint         False      Display tab completion hint even when completion suggestions print
 debug                    False      Show full traceback on exception
 echo                     False      Echo command issued into output
 editor                   vim        Program used by 'edit'
 feedback_to_output       False      Include nonessentials in '|' and '>' results
 foreground_color         cyan       Foreground color to use with echo command
 max_completion_items     50         Maximum number of CompletionItems to display during tab completion
 quiet                    False      Don't print nonessential feedback
 scripts_add_to_history   True       Scripts and pyscripts add commands to history
 timing                   False      Report execution times
```

Any of these user-settable parameters can be set while running your app with the `set` command like
so:

```text
(Cmd) set allow_style Never
```

See [Settings](./settings.md) for more information.

### shell

Execute a command as if at the operating system shell prompt:

```text
(Cmd) shell pwd -P
/usr/local/bin
```

### shortcuts

This command lists available shortcuts. See [Shortcuts](./shortcuts_aliases_macros.md#shortcuts) for
more information.

## Remove Builtin Commands

Developers may not want to offer all the commands built into [cmd2.Cmd][] to users of their
application. To remove a command you must delete the method implementing that command from the
[cmd2.Cmd][] object at runtime. For example, if you wanted to remove the [shell](#shell) command
from your application:

```py
class NoShellApp(cmd2.Cmd):
    """A simple cmd2 application."""

    delattr(cmd2.Cmd, 'do_shell')
```
