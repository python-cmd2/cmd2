# Next Steps

Once your current application is using `cmd2`, you can start to expand the functionality by levering other `cmd2` features. The three ideas here will get you started. Browse the rest of the [Features](../features/index.md) to see what else `cmd2` can help you do.

## Argument Parsing

For all but the simplest of commands, it's probably easier to use [argparse](https://docs.python.org/3/library/argparse.html) to parse user input. `cmd2` provides a `@with_argparser()` decorator which associates an `ArgumentParser` object with one of your commands. Using this method will:

1.  Pass your command a [Namespace](https://docs.python.org/3/library/argparse.html#argparse.Namespace) containing the arguments instead of a string of text.
2.  Properly handle quoted string input from your users.
3.  Create a help message for you based on the `ArgumentParser`.
4.  Give you a big headstart adding [Tab Completion](../features/completion.md) to your application.
5.  Make it much easier to implement subcommands (i.e. `git` has a bunch of subcommands such as `git pull`, `git diff`, etc).

There's a lot more about [Argument Processing](../features/argument_processing.md) if you want to dig in further.

## Help

If you have lot of commands in your application, `cmd2` can categorize those commands using a one line decorator `@with_category()`. When a user types `help` the available commands will be organized by the category you specified.

If you were already using `argparse` or decided to switch to it, you can easily [standardize all of your help messages](../features/argument_processing.md#help-messages) to be generated by your argument parsers and displayed by `cmd2`. No more help messages that don't match what the code actually does.

## Generating Output

If your program generates output by printing directly to `sys.stdout`, you should consider switching to `cmd2.Cmd.poutput`, `cmd2.Cmd.perror`, and `cmd2.Cmd.pfeedback`. These methods work with several of the built in [Settings](../features/settings.md) to allow the user to view or suppress feedback (i.e. progress or status output). They also properly handle ansi colored output according to user preference. Speaking of colored output, you can use any color library you want, or use the included `cmd2.ansi.style` function. These and other related topics are covered in [Generating Output](../features/generating_output.md).