# Commands

`cmd2` is designed to make it easy for you to create new commands. These commands form the backbone
of your application. If you started writing your application using
[cmd](https://docs.python.org/3/library/cmd.html), all the commands you have built will work when
you move to `cmd2`. However, there are many more capabilities available in `cmd2` which you can take
advantage of to add more robust features to your commands, and which makes your commands easier to
write. Before we get to all the good stuff, let's briefly discuss how to create a new command in
your application.

## Basic Commands

The simplest `cmd2` application looks like this:

```py
#!/usr/bin/env python
"""A simple cmd2 application."""
import cmd2


class App(cmd2.Cmd):
    """A simple cmd2 application."""


if __name__ == '__main__':
    import sys
    c = App()
    sys.exit(c.cmdloop())
```

This application subclasses [cmd2.Cmd][] but has no code of its own, so all functionality (and
there's quite a bit) is inherited. Let's create a simple command in this application called `echo`
which outputs any arguments given to it. Add this method to the class:

```py
def do_echo(self, line):
    self.poutput(line)
```

When you type input into the `cmd2` prompt, the first space-delimited word is treated as the command
name. `cmd2` looks for a method called `do_commandname`. If it exists, it calls the method, passing
the rest of the user input as the first argument. If it doesn't exist `cmd2` prints an error
message. As a result of this behavior, the only thing you have to do to create a new command is to
define a new method in the class with the appropriate name. This is exactly how you would create a
command using the [cmd](https://docs.python.org/3/library/cmd.html) module which is part of the
python standard library.

!!! note

    See [Generating Output](./generating_output.md) if you are unfamiliar with the
    [poutput()][cmd2.Cmd.poutput] method.

## Statements

A command is passed one argument: a string which contains all the rest of the user input. However,
in `cmd2` this string is actually a [Statement][cmd2.Statement] object, which is a subclass of `str`
to retain backwards compatibility with `cmd`.

`cmd2` has a much more sophisticated parsing engine than what's included in the
[cmd](https://docs.python.org/3/library/cmd.html) module. This parsing handles:

- quoted arguments
- output redirection and piping
- multi-line commands
- shortcut, alias, and macro expansion

In addition to parsing all of these elements from the user input, `cmd2` also has code to make all
of these items work; it's almost transparent to you and to the commands you write in your own
application. However, by passing your command the `Statement` object instead of just a plain string,
you can get visibility into what `cmd2` has done with the user input before your command got it. You
can also avoid writing a bunch of parsing code, because `cmd2` gives you access to what it has
already parsed.

A `Statement` object is a subclass of `str` that contains the following attributes:

**command**

: Name of the command called. You already know this because of the method `cmd2` called, but it can
sometimes be nice to have it in a string, i.e. if you want your error messages to contain the
command name.

**args**

: A string containing the arguments to the command with output redirection or piping to shell
commands removed. It turns out that the "string" value of the `Statement` object has all the output
redirection and piping clauses removed as well. Quotes remain in the string.

**command_and_args**

: A string of just the command and the arguments, with output redirection or piping to shell
commands removed.

**argv**

: A list of arguments a-la `sys.argv`, including the command as `argv[0]` and the subsequent
arguments as additional items in the list. Quotes around arguments will be stripped as will any
output redirection or piping portions of the command.

**raw**

: Full input exactly as typed by the user.

**terminator**

: Character used to end a multiline command. You can configure multiple termination characters, and
this attribute will tell you which one the user typed.

For many simple commands, like the `echo` command above, you can ignore the `Statement` object and
all of its attributes and just use the passed value as a string. You might choose to use the `argv`
attribute to do more sophisticated argument processing. Before you go too far down that path, you
should check out the [Argument Processing](./argument_processing.md) functionality included with
`cmd2`.

## Return Values

Most commands should return nothing (either by omitting a `return` statement, or by `return None`.
This indicates that your command is finished (with or without errors), and that `cmd2` should prompt
the user for more input.

If you return `True` or any
[Truthy](https://www.freecodecamp.org/news/truthy-and-falsy-values-in-python/) value from a command
method, that indicates to `cmd2` that it should stop prompting for user input and cleanly exit.
`cmd2` already includes a `quit` command, but if you wanted to make another one called `finish` you
could:

```py
def do_finish(self, line):
    """Exit the application"""
    return True
```

## Exit Codes

`cmd2` has basic infrastructure to support POSIX shell exit codes. The `cmd2.Cmd` object sets an
`exit_code` attribute to zero when it is instantiated. The value of this attribute is returned from
the `cmdloop()` call. Therefore, if you don't do anything with this attribute in your code,
`cmdloop()` will (almost) always return zero. There are a few built-in `cmd2` commands which set
`exit_code` to `1` if an error occurs.

You can use this capability to easily return your own values to the operating system shell:

```py
#!/usr/bin/env python
"""A simple cmd2 application."""
import cmd2


class App(cmd2.Cmd):
    """A simple cmd2 application."""

def do_bail(self, line):
    """Exit the application"""
    self.perror("fatal error, exiting")
    self.exit_code = 2
    return True

if __name__ == '__main__':
    import sys
    c = App()
    sys.exit(c.cmdloop())
```

If the app was run from the `bash` operating system shell, then you would see the following
interaction:

```sh
(Cmd) bail
fatal error, exiting
$ echo $?
2
```

Raising `SystemExit(code)` or calling `sys.exit(code)` in a command or hook function also sets
`self.exit_code` and stops the program.

## Exception Handling

You may choose to catch and handle any exceptions which occur in a command method. If the command
method raises an exception, `cmd2` will catch it and display it for you. The
[debug setting](./settings.md#debug) controls how the exception is displayed. If `debug` is `False`,
which is the default, `cmd2` will display the exception name and message. If `debug` is `True`,
`cmd2` will display a traceback, and then display the exception name and message.

There are a few exceptions which commands can raise that do not print as described above:

- `cmd2.exceptions.SkipPostcommandHooks` - all postcommand hooks are skipped and no exception prints
- `cmd2.exceptions.Cmd2ArgparseError` - behaves like `SkipPostcommandHooks`
- `SystemExit` - `stop` will be set to `True` in an attempt to stop the command loop
- `KeyboardInterrupt` - raised if running in a text script and `stop` isn't already True to stop the
  script

All other `BaseExceptions` are not caught by `cmd2` and will be raised.

## Disabling or Hiding Commands

See [Disabling Commands](./disable_commands.md) for details of how to:

- Remove commands included in `cmd2`
- Hide commands from the help menu
- Dynamically disable and re-enable commands at runtime

## Modular Commands and Loading/Unloading Commands

See [Modular Commands](./modular_commands.md) for details of how to:

- Define commands in separate [CommandSet][cmd2.CommandSet] modules
- Dynamically load or unload commands at runtime
