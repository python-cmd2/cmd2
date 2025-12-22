# Getting Started

Here's a quick walkthrough of the simple
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example application which demonstrates many features of `cmd2`:

- [Settings](../features/settings.md)
- [Commands](../features/commands.md)
- [Argument Processing](../features/argument_processing.md)
- [Generating Output](../features/generating_output.md)
- [Help](../features/help.md)
- [Shortcuts](../features/shortcuts_aliases_macros.md#shortcuts)
- [Multiline Commands](../features/multiline_commands.md)
- [History](../features/history.md)

If you don't want to type as we go, here is the complete source (you can click to expand and then
click the **Copy** button in the top-right):

!!! example "getting_started.py"

    ```py
    --8<-- "examples/getting_started.py"
    ```

## Basic Application

First we need to create a new `cmd2` application. Create a new file `getting_started.py` with the
following contents:

```py
#!/usr/bin/env python
"""A basic cmd2 application."""
import cmd2


class BasicApp(cmd2.Cmd):
    """Cmd2 application to demonstrate many common features."""


if __name__ == '__main__':
    import sys
    app = BasicApp()
    sys.exit(app.cmdloop())
```

We have a new class `BasicApp` which is a subclass of [cmd2.Cmd][]. When we tell Python to run our
file like this:

```shell
$ python getting_started.py
```

The application creates an instance of our class, and calls the [cmd2.Cmd.cmdloop][] method. This
method accepts user input and runs commands based on that input. Because we subclassed `cmd2.Cmd`,
our new app already has a bunch of built-in features.

Congratulations, you have a working `cmd2` app. You can run it, and then type `quit` to exit.

## Create a New Setting

Before we create our first command, we are going to add a new setting to this app. `cmd2` includes
robust support for [Settings](../features/settings.md). You configure settings during object
initialization, so we need to add an initializer to our class:

```py
def __init__(self):
    super().__init__()

    # Make maxrepeats settable at runtime
    self.maxrepeats = 3
    self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command', self))
```

In that initializer, the first thing to do is to make sure we initialize `cmd2`. That's what the
`super().__init__()` line does. Next create an attribute to hold the setting. Finally, call the
[cmd2.Cmd.add_settable][] method with a new instance of a [cmd2.utils.Settable][] class. Now if you
run the script, and enter the `set` command to see the settings, like this:

```shell
$ python getting_started.py
(Cmd) set
```

you will see our `maxrepeats` setting show up with its default value of `3`.

## Create A Command

Now we will create our first command, called `speak`, which will echo back whatever we tell it to
say. We are going to use an [argument processor](../features/argument_processing.md) so the `speak`
command can shout and talk Pig Latin. We will also use some built in methods for
[generating output](../features/generating_output.md). Add this code to `getting_started.py`, so
that the `speak_parser` attribute and the `do_speak()` method are part of the `BasicApp()` class:

```py
speak_parser = cmd2.Cmd2ArgumentParser()
speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
speak_parser.add_argument('words', nargs='+', help='words to say')

@cmd2.with_argparser(speak_parser)
def do_speak(self, args):
    """Repeats what you tell me to."""
    words = []
    for word in args.words:
        if args.piglatin:
            word = '%s%say' % (word[1:], word[0])
        if args.shout:
            word = word.upper()
        words.append(word)
    repetitions = args.repeat or 1
    for _ in range(min(repetitions, self.maxrepeats)):
        # .poutput handles newlines, and accommodates output redirection too
        self.poutput(' '.join(words))
```

Up at the top of the script, you'll also need to add:

```py
import argparse
```

There's a bit to unpack here, so let's walk through it. We created `speak_parser`, which uses the
[argparse](https://docs.python.org/3/library/argparse.html) module from the Python standard library
to parse command line input from a user. So far, there is nothing specific to `cmd2`.

There is also a new method called `do_speak()`. In both
[cmd](https://docs.python.org/3/library/cmd.html) and `cmd2`, methods that start with `do_` become
new commands, so by defining this method we have created a command called `speak`.

Note the `cmd2.decorators.with_argparser` decorator on the `do_speak()` method. This decorator does
3 useful things for us:

1.  It tells `cmd2` to process all input for the `speak` command using the argparser we defined. If
    the user input doesn't meet the requirements defined by the argparser, then an error will be
    displayed for the user.
1.  It alters our `do_speak` method so that instead of receiving the raw user input as a parameter,
    we receive the namespace from the argument parser.
1.  It creates a help message for us based on the argparser.

You can see in the body of the method how we use the namespace from the argparser (passed in as the
variable `args`). We build a list of words which we will output, honoring both the `--piglatin` and
`--shout` options.

At the end of the method, we use our `maxrepeats` setting as an upper limit to the number of times
we will print the output.

The last thing you'll notice is that we used the `self.poutput()` method to display our output.
`poutput()` is a method provided by `cmd2`, which I strongly recommend you use any time you want to
[generate output](../features/generating_output.md). It provides the following benefits:

1.  Allows the user to redirect output to a text file or pipe it to a shell process
1.  Gracefully handles `BrokenPipeError` exceptions for redirected output
1.  Makes the output show up in a [transcript](../features/transcripts.md)
1.  Honors the setting to [strip embedded ANSI sequences](../features/settings.md#allow_style)
    (typically used for background and foreground colors)

Go run the script again, and try out the `speak` command. Try typing `help speak`, and you will see
a lovely usage message describing the various options for the command.

With those few lines of code, we created a [command](../features/commands.md), used an
[Argument Processor](../features/argument_processing.md), added a nice
[help message](../features/help.md) for our users, and
[generated some output](../features/generating_output.md).

## Shortcuts

`cmd2` has several capabilities to simplify repetitive user input:
[Shortcuts, Aliases, and Macros](../features/shortcuts_aliases_macros.md). Let's add a shortcut to
our application. Shortcuts are character strings that can be used instead of a command name. For
example, `cmd2` has support for a shortcut `!` which runs the `shell` command. So instead of typing
this:

```shell
(Cmd) shell ls -al
```

you can type this:

```shell
(Cmd) !ls -al
```

Let's add a shortcut for our `speak` command. Change the `__init__()` method so it looks like this:

```py
def __init__(self):
    shortcuts = cmd2.DEFAULT_SHORTCUTS
    shortcuts.update({'&': 'speak'})
    super().__init__(shortcuts=shortcuts)

    # Make maxrepeats settable at runtime
    self.maxrepeats = 3
    self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command', self))
```

Shortcuts are passed to the `cmd2` initializer, and if you want the built-in shortcuts of `cmd2` you
have to pass them. These shortcuts are defined as a dictionary, with the key being the shortcut, and
the value containing the command. When using the default shortcuts and adding your own, it's a good
idea to use the `.update()` method to modify the dictionary. This way, if you add a shortcut that
happens to already be in the default set, yours will override, and you won't get any errors at
runtime.

Run your app again, and type:

```shell
(Cmd) shortcuts
```

to see the list of all the shortcuts, including the one for speak that we just created.

## Multiline Commands

Some use cases benefit from commands that span more than one line. For example, you might want the
ability for your user to type in a SQL command, which can often span lines and which are terminated
with a semicolon. Let's add a [multiline command](../features/multiline_commands.md) to our
application. First we'll create a new command called `orate`. This code shows both the definition of
our `speak` command, and the `orate` command:

```py
@cmd2.with_argparser(speak_parser)
def do_speak(self, args):
    """Repeats what you tell me to."""
    words = []
    for word in args.words:
        if args.piglatin:
            word = '%s%say' % (word[1:], word[0])
        if args.shout:
            word = word.upper()
        words.append(word)
    repetitions = args.repeat or 1
    for _ in range(min(repetitions, self.maxrepeats)):
        # .poutput handles newlines, and accommodates output redirection too
        self.poutput(' '.join(words))

# orate is a synonym for speak which takes multiline input
do_orate = do_speak
```

With the new command created, we need to tell `cmd2` to treat that command as a multi-line command.
Modify the super initialization line to look like this:

```py
super().__init__(multiline_commands=['orate'], shortcuts=shortcuts)
```

Now when you run the example, you can type something like this:

```text
(Cmd) orate O for a Muse of fire, that would ascend
> The brightest heaven of invention,
> A kingdom for a stage, princes to act
> And monarchs to behold the swelling scene! ;
```

Notice the prompt changes to indicate that input is still ongoing. `cmd2` will continue prompting
for input until it sees an unquoted semicolon (the default multi-line command termination
character).

## History

`cmd2` tracks the history of the commands that users enter. As a developer, you don't need to do
anything to enable this functionality, you get it for free. If you want the history of commands to
persist between invocations of your application, you'll need to do a little work. The
[History](../features/history.md) page has all the details.

Users can access command history using two methods:

- The [readline](https://docs.python.org/3/library/readline.html) library which provides a Python
  interface to the [GNU readline library](https://en.wikipedia.org/wiki/GNU_Readline)
- The `history` command which is built-in to `cmd2`

From the prompt in a `cmd2`-based application, you can press `Control-p` to move to the previously
entered command, and `Control-n` to move to the next command. You can also search through the
command history using `Control-r`. The
[GNU Readline User Manual](http://man7.org/linux/man-pages/man3/readline.3.html) has all the
details, including all the available commands, and instructions for customizing the key bindings.

The `history` command allows a user to view the command history, and select commands from history by
number, range, string search, or regular expression. With the selected commands, users can:

- Re-run the commands
- Edit the selected commands in a text editor, and run them after the text editor exits
- Save the commands to a file
- Run the commands, saving both the commands and their output to a file

Learn more about the `history` command by typing `history -h` at any `cmd2` input prompt, or by
exploring [Command History For Users](../features/history.md#for-users).

## Conclusion

You've just created a simple, but functional command line application. With minimal work on your
part, the application leverages many robust features of `cmd2`. To learn more you can:

- Dive into all of the [Features](../features/index.md) that `cmd2` provides
- Look at more [Examples](../examples/index.md)
- Browse the [API Reference](../api/index.md)
