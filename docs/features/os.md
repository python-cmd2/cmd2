# Integrating with the OS

## How to redirect output

See [Output Redirection and Pipes](./redirection.md#output-redirection-and-pipes)

## Executing OS commands from within `cmd2`

`cmd2` includes a `shell` command which executes its arguments in the operating system shell:

    (Cmd) shell ls -al

If you use the default [Shortcuts](./shortcuts_aliases_macros.md#shortcuts) defined in `cmd2` you'll
get a `!` shortcut for `shell`, which allows you to type:

    (Cmd) !ls -al

!!! note

    `cmd2` provides user-friendly tab completion throughout the process of running a shell command -
    first for the shell command name itself, and then for file paths in the argument section.

    However, a `cmd2` application effectively **becomes** the shell, so if you have _extra_ shell
    completion configured for your particular shell such as `bash`, `zsh`, `fish`, etc. then this
    will not be available within `cmd2`.

## Editors

`cmd2` includes the built-in `edit` command which runs a text editor and optionally opens a file
with it:

    (Cmd) edit foo.txt

The editor used is determined by the `editor` settable parameter and can be either a text editor
such as **vim** or a graphical editor such as **VSCode**. To set it:

    set editor <program_name>

If you have the `EDITOR` environment variable set, then this will be the default value for `editor`.
If not, then `cmd2` will attempt to search for any in a list of common editors for your operating
system.

## Terminal pagers

Output of any command can be displayed one page at a time using the [cmd2.Cmd.ppaged][] method.

While the bottom toolbar is running, `ppaged()` uses an embedded pager so the toolbar remains
visible and continues refreshing. It supports scrolling, search, and chopped lines. Set
`self.use_builtin_pager = False` to use the configured external `pager`/`pager_chop` commands
instead. Anywhere the toolbar is not running, such as a command invoked outside the command loop,
`ppaged()` uses the external pager regardless of this setting. See
[Bottom Toolbar](./prompt.md#bottom-toolbar) for controls and details.

Alternatively, a terminal pager can be invoked directly using the ability to run shell commands with
the `!` shortcut like so:

    (Cmd) !less foo.txt

!!! warning

    Once you are in an external terminal pager, that program temporarily has control of your terminal,
    **NOT** `cmd2`. Typically you can use either the arrow keys or `<PageUp>`/`<PageDown>` keys to
    scroll around or type `q` to quit the pager and return control to your `cmd2` application.

## Exit codes

The `self.exit_code` attribute of your `cmd2` application controls what exit code is returned from
`cmdloop()` when it completes. It is your job to make sure that this exit code gets sent to the
shell when your application exits by calling `sys.exit(app.cmdloop())`.

## Invoking With Arguments

Typically you would invoke a `cmd2` program by typing:

    $ python mycmd2program.py

or:

    $ mycmd2program.py

Either of these methods will launch your program and enter the `cmd2` command loop, which allows the
user to enter commands, which are then executed by your program.

You may want to execute commands in your program without prompting the user for any input. There are
several ways you might accomplish this task. One is to pipe commands and their arguments into your
program via standard input. You don't need to do anything to your program in order to use this
technique. Here's a demonstration using the `examples/cmd_as_argument.py` included in the source
code of `cmd2`:

    $ echo "speak -p some words" | uv run examples/cmd_as_argument.py
    omesay ordsway

Using this same approach you could create a text file containing the commands you would like to run,
one command per line in the file. Say your file was called `somecmds.txt`. To run the commands in
the text file using your `cmd2` program (from a Windows command prompt):

    c:\cmd2> type somecmds.txt | uv run examples/cmd_as_argument.py
    omesay ordsway

By default, `cmd2` programs also look for commands passed as arguments from the operating system
shell, and execute those commands before entering the command loop:

    $ uv run examples/cmd_as_argument.py help

    Documented Commands
    ───────────────────
    alias  help     macro   orate  run_pyscript  say  shell      speak
    edit   history  mumble  quit   run_script    set  shortcuts

    (Cmd)

You may need more control over command line arguments passed from the operating system shell. For
example, you might have a command inside your `cmd2` program which itself accepts arguments, and
maybe even option strings. Say you wanted to run the `speak` command from the operating system
shell, but have it say it in pig latin - just group the command and its arguments inside either
double or single quotes:

    $ uv run examples/cmd_as_argument.py "speak -p hello there"
    ellohay heretay
    (Cmd)

If you want to start your application using a custom `argparse` parser to collect high-level
application arguments but still want to be able to pass extra unknown arguments as commands at
invocation, then see the
[argparse_example.py](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_example.py)
example. Using this methodology you can call it like so:

    $ uv run examples/argparse_example.py -c blue help

Check the source code of this example, especially the `if __name__ == "__main__":` block, to see the
technique.

### Automating cmd2 apps from other CLI/CLU tools

While `cmd2` is designed to create **interactive** command-line applications which enter a
Read-Evaluate-Print-Loop (REPL), there are a great many times when it would be useful to use a
`cmd2` application as a run-and-done command-line utility for purposes of automation and scripting.

This is easily achieved by combining the following capabilities of `cmd2`:

1.  Ability to invoke a `cmd2` application with arguments
2.  Ability to set an exit code when leaving a `cmd2` application
3.  Ability to exit a `cmd2` application with the `quit` command

Here is a simple example which doesn't require the quit command since the custom `exit` command
quits while returning an exit code:

    $ uv run examples/exit_code.py "exit 23"
    'examples/exit_code.py' exiting with code: 23
    $ echo $?
    23

Here is another example using `quit`:

    $ uv run examples/cmd_as_argument.py "speak -p hello there" quit
    ellohay heretay
    $
