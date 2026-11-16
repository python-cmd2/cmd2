# Completion

`cmd2.Cmd` adds tab completion of file system paths for all built-in commands where it makes sense,
including:

- [edit](./builtin_commands.md#edit)
- [run_pyscript](./builtin_commands.md#run_pyscript)
- [run_script](./builtin_commands.md#run_script)
- [shell](./builtin_commands.md#shell)

`cmd2.Cmd` also adds tab completion of shell commands to the [shell](./builtin_commands.md#shell)
command.

It is easy to add identical file system path completion to your own custom commands. Suppose you
have defined a custom command `foo` by implementing the `do_foo` method. To enable path completion
for the `foo` command, then add a line of code similar to the following to your class which inherits
from `cmd2.Cmd`:

```py
complete_foo = cmd2.Cmd.path_complete
```

This will effectively define the `complete_foo` prompt-toolkit completer method in your class and
make it utilize the same path completion logic as the built-in commands.

The built-in logic allows for a few more advanced path completion capabilities, such as cases where
you only want to match directories. Suppose you have a custom command `bar` implemented by the
`do_bar` method. You can enable path completion of directories only for this command by adding a
line of code similar to the following to your class which inherits from `cmd2.Cmd`:

```py
# Make sure you have an "import functools" somewhere at the top
complete_bar = functools.partialmethod(cmd2.Cmd.path_complete, path_filter=os.path.isdir)
```

## Special Characters in Paths

Path and shell command completion match the text being completed literally. Glob characters such as
`*`, `?`, and `[` are never expanded, so a file named `my*file.txt` or `notes[2026].txt` completes
like any other. The one exception is a leading `~`, which refers to a user's home directory as it
does in a shell.

Completion results are literal names too. `cmd2` does not escape them, because it has no way of
knowing how a command will use a path. Most commands use a path directly in Python, where the
literal name is exactly what is wanted. What `cmd2` does do is add quotes when a completed path or
shell command has a character which is special to a shell:

```text
(Cmd) !ls my*<TAB>
(Cmd) !ls "my*file.txt"
```

The quotes keep a shell from interpreting the name if the command line is passed to one, as the
[shell](./builtin_commands.md#shell) command and a [pipe](./redirection.md) do. They also keep
`cmd2` from treating a character like `;` or `>` in the name as part of its own syntax. `cmd2`
removes the quotes before passing the argument to a command, unless that command asked to preserve
them.

On POSIX systems the characters which get a name quoted are a space, a quote character, `*`, `?`,
`[` when a `]` follows it, `{`, `}`, `(`, `)`, `<`, `>`, `|`, `&`, `;`, `$`, a backtick, a
backslash, and a leading `#`. Single quotes are used when a name has a `$`, a backtick, or a
backslash, since a shell still interprets those within double quotes. On Windows the characters are
a space, `'`, `&`, `(`, `)`, `^`, and `;`, and the quotes are always double quotes.

There are limits to this:

- The quotes go around the whole argument, so when several matches are offered and only one of them
  needs quotes, they all get them.
- A name with a single quote in it is wrapped in double quotes, so a `$`, a backtick, or a backslash
  in that same name is still interpreted by a shell.
- A `%` in a name is still interpreted by `cmd.exe` on Windows.
- Only paths and shell commands completed by `cmd2` are quoted this way. Results from your own
  completers and choices are only quoted when one of them contains a space.

## Included Tab Completion Functions

[cmd2.Cmd][] provides the following tab completion functions

- [basic_complete][cmd2.Cmd.basic_complete] - helper method for tab completion against a list

- [path_complete][cmd2.Cmd.path_complete] - helper method provides flexible tab completion of file
  system paths

    > - See the
    >   [paged_output](https://github.com/python-cmd2/cmd2/blob/main/examples/paged_output.py)
    >   example for a simple use case
    > - See the
    >   [python_scripting](https://github.com/python-cmd2/cmd2/blob/main/examples/python_scripting.py)
    >   example for a more full-featured use case

- [delimiter_complete][cmd2.Cmd.delimiter_complete] - helper method for tab completion against a
  list but each match is split on a delimiter

    > - See the
    >   [basic_completion](https://github.com/python-cmd2/cmd2/blob/main/examples/basic_completion.py)
    >   example for a demonstration of how to use this feature

## Raising Exceptions During Completion

There are times when an error occurs while tab completing and a message needs to be reported to the
user. These include the following example cases:

- Reading a database to retrieve a tab completion data set failed
- A previous command line argument that determines the data set being completed is invalid
- Tab completion hints

`cmd2` provides the [CompletionError][cmd2.CompletionError] exception class for this capability. If
an error occurs in which it is more desirable to display a message than a stack trace, then raise a
`CompletionError`. By default, the message displays in red like an error. However, `CompletionError`
has a member called `apply_style`. Set this False if the error style should not be applied. For
instance, `ArgparseCompleter` sets it to False when displaying completion hints.

## Tab Completion Using the argparse Decorator {: #argparse-based }

When using `cmd2`'s [@with_argparser][cmd2.with_argparser] decorator, `cmd2` provides automatic tab
completion of flag names.

Tab completion of argument values can be configured by using one of three parameters to
`Cmd2ArgumentParser.add_argument()`.

- `choices`
- `choices_provider`
- `completer`

See the
[argparse_example](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_example.py)
example for a demonstration of how to use the `choices` parameter. See the
[argparse_completion](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_completion.py)
example for a demonstration of how to use the `choices_provider` parameter. See the
[argparse_example](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_example.py) or
[argparse_completion](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_completion.py)
example for a demonstration of how to use the `completer` parameter.

When tab completing flags or argument values for a `cmd2` command using the `@with_argparser`
decorator, `cmd2` keeps track of state so that once a flag has already previously been provided, it
won't attempt to tab complete it again. When no completion results exist, a hint for the current
argument will be displayed to help the user.

## CompletionItem For Providing Extra Context

When tab completing things like a unique ID from a database, it can often be beneficial to provide
the user with some extra context about the item being completed, such as a description. To
facilitate this, `cmd2` defines the [CompletionItem][cmd2.CompletionItem] class which can be
returned from any of the 3 completion parameters: `choices`, `choices_provider`, and `completer`.

See the
[argparse_completion](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_completion.py)
example or the implementation of the built-in [set](./builtin_commands.md#set) command for
demonstration of how this is used.

## Custom Completion with `read_input()`

`cmd2` provides [cmd2.Cmd.read_input][] as an alternative to Python's `input()` function.
`read_input` supports configurable tab completion and up-arrow history at the prompt. See
[read_input](https://github.com/python-cmd2/cmd2/blob/main/examples/read_input.py) example for a
demonstration.

## Custom Completion Menu Colors

`cmd2` provides the ability to customize the foreground and background colors of the completion menu
items and their associated help text. See
[Customizing Completion Menu Colors](./theme.md#customizing-completion-menu-colors) in the Theme
documentation for more details.

## For More Information

See [cmd2's argparse_utils API](../api/argparse_utils.md) for a more detailed discussion of argparse
completion.
