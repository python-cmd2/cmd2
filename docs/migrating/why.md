# Why cmd2

## cmd

[cmd][cmd] is the Python Standard Library's module for creating simple interactive command-line
applications. [cmd][cmd] is an extremely bare-bones framework which leaves a lot to be desired. It
doesn't even include a built-in way to exit from an application!

Since the API provided by [cmd][cmd] provides the foundation on which `cmd2` is based, understanding
the use of [cmd][cmd] is the first step in learning the use of `cmd2`. Once you have read the
[cmd](#cmd) docs, return here to learn the ways that `cmd2` differs from [cmd][cmd].

## cmd2

`cmd2` is a batteries-included extension of [cmd][cmd], which provides a wealth of functionality to
make it quicker and easier for developers to create feature-rich interactive command-line
applications which delight customers.

`cmd2` can be used as a drop-in replacement for [cmd][cmd] with a few minor discrepancies as
discussed in the [Incompatibilities](incompatibilities.md) section. Simply importing `cmd2` in place
of [cmd][cmd] will add many features to an application without any further modifications. Migrating
to `cmd2` will also open many additional doors for making it possible for developers to provide a
top-notch interactive command-line experience for their users.

!!! warning

    As of version 4.0.0, `cmd2` does not have an actual dependency on `cmd`. `cmd2` is mostly API compatible with `cmd2`.
    See [Incompatibilities](./incompatibilities.md) for the few documented incompatibilities.

## Automatic Features

After switching from [cmd][cmd] to `cmd2`, your application will have the following new features and
capabilities, without you having to do anything:

- More robust [History](../features/history.md). Both [cmd][cmd] and `cmd2` have readline history,
  but `cmd2` also has a robust `history` command which allows you to edit prior commands in a text
  editor of your choosing, re-run multiple commands at a time, save prior commands as a script to be
  executed later, and much more.
- Users can redirect output to a file or pipe it to some other operating system command. You did
  remember to use `self.stdout` instead of `sys.stdout` in all of your print functions, right? If
  you did, then this will work out of the box. If you didn't, you'll have to go back and fix them.
  Before you do, you should consider the various ways `cmd2` has of
  [Generatoring Output](../features/generating_output.md).
- Users can load [script files](../features/scripting.md), which contain a series of commands to be
  executed.
- Users can create [Shortcuts, Aliases, and Macros](../features/shortcuts_aliases_macros.md) to
  reduce the typing required for repetitive commands.
- [Embedded Python and/or IPython shells](../features/embedded_python_shells.md) allow a user to
  execute Python code from within your `cmd2` app. How meta.
- [Clipboard Integration](../features/clipboard.md) allows you to save command output to the
  operating system clipboard.
- A built-in [Timer](../features/misc.md#Timer) can show how long it takes a command to execute
- A [Transcript](../features/transcripts.md) is a file which contains both the input and output of a
  successful session of a `cmd2`-based app. The transcript can be played back into the app as a unit
  test.

## Next Steps

In addition to the features you get with no additional work, `cmd2` offers a broad range of
additional capabilities which can be easily added to your application. [Next Steps](next_steps.md)
has some ideas of where you can start, or you can dig in to all the
[Features](../features/index.md).

[cmd]: https://docs.python.org/3/library/cmd
