# cmd2 Examples

The [examples](https://github.com/python-cmd2/cmd2/tree/master/examples) directory within the `cmd2`
repository contains a number of simple self-contained examples which each demonstrate a few
particular features of `cmd2`. None of them are representative of a full real-world complex `cmd2`
application, if you are looking for that then see
[Projects using cmd2](https://github.com/python-cmd2/cmd2?tab=readme-ov-file#projects-using-cmd2).

## List of cmd2 examples

Here is the list of examples in alphabetical order by filename along with a brief description of
each:

- [alias_startup.py](https://github.com/python-cmd2/cmd2/blob/master/examples/alias_startup.py)
    - Demonstrates how to add custom command aliases and how to run an initialization script at
      startup
- [arg_decorators.py](https://github.com/python-cmd2/cmd2/blob/master/examples/arg_decorators.py)
    - Demonstrates how to use the `cmd2.with_argparser` decorator to specify command arguments using
      [argparse](https://docs.python.org/3/library/argparse.html)
- [arg_print.py](https://github.com/python-cmd2/cmd2/blob/master/examples/arg_print.py)
    - Demonstrates how arguments and options get parsed and passed to commands and shows how
      shortcuts work
- [argparse_completion.py](https://github.com/python-cmd2/cmd2/blob/master/examples/argparse_completion.py)
    - Shows how to integrate tab-completion with argparse-based commands
- [async_printing.py](https://github.com/python-cmd2/cmd2/blob/master/examples/async_printing.py)
    - Shows how to asynchronously print alerts, update the prompt in realtime, and change the window
      title
- [basic.py](https://github.com/python-cmd2/cmd2/blob/master/examples/basic.py)
    - Shows how to add a command, add help for it, and create persistent command history for your
      application
- [basic_completion.py](https://github.com/python-cmd2/cmd2/blob/master/examples/basic_completion.py)
    - Show how to enable custom tab completion by assigning a completer function to `do_*` commands
- [cmd2_as_argument.py](https://github.com/python-cmd2/cmd2/blob/master/examples/cmd_as_argument.py)
    - Demonstrates how to accept and parse command-line arguments when invoking a cmd2 application
- [colors.py](https://github.com/python-cmd2/cmd2/blob/master/examples/colors.py)
    - Show various ways of using colorized output within a cmd2 application
- [custom_parser.py](https://github.com/python-cmd2/cmd2/blob/master/examples/custom_parser.py)
    - Demonstrates how to create your own customer `Cmd2ArgumentParser`; used by the
      `override_parser.py` example
- [decorator_example.py](https://github.com/python-cmd2/cmd2/blob/master/examples/decorator_example.py)
    - Shows how to use cmd2's various argparse decorators to processes command-line arguments
- [default_categories.py](https://github.com/python-cmd2/cmd2/blob/master/examples/default_categories.py)
    - Demonstrates usage of `@with_default_category` decorator to group and categorize commands and
      `CommandSet` use
- [dynamic_commands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/dynamic_commands.py)
    - Shows how `do_*` commands can be dynamically created programatically at runtime
- [environment.py](https://github.com/python-cmd2/cmd2/blob/master/examples/environment.py)
    - Shows how to create custom `cmd2.Settable` parameters which serve as internal environment
      variables
- [event_loops.py](https://github.com/python-cmd2/cmd2/blob/master/examples/event_loops.py)
    - Shows how to integrate a `cmd2` application with an external event loop which isn't managed by
      `cmd2`
- [example.py](https://github.com/python-cmd2/cmd2/blob/master/examples/example.py)
    - This example is intended to demonstrate `cmd2's` build-in transcript testing capability
- [exit_code.py](https://github.com/python-cmd2/cmd2/blob/master/examples/exit_code.py)
    - Show how to emit a non-zero exit code from your `cmd2` application when it exits
- [first_app.py](https://github.com/python-cmd2/cmd2/blob/master/examples/first_app.py)
    - Short application that demonstrates 8 key features: Settings, Commands, Argument Parsing,
      Generating Output, Help, Shortcuts, Multiple Commands, and History
- [hello_cmd2.py](https://github.com/python-cmd2/cmd2/blob/master/examples/hello_cmd2.py)
    - Completely bare-bones `cmd2` application suitable for rapid testing and debugging of `cmd2`
      itself
- [help_categories.py](https://github.com/python-cmd2/cmd2/blob/master/examples/help_categories.py)
    - Demonstrates command categorization and its impact on the output of the built-in `help`
      command
- [hooks.py](https://github.com/python-cmd2/cmd2/blob/master/examples/hooks.py)
    - Shows how to use various `cmd2` application lifecycle hooks
- [initialization.py](https://github.com/python-cmd2/cmd2/blob/master/examples/initialization.py)
    - Shows how to colorize output, use multiline command, add persistent history, and more
- [migrating.py](https://github.com/python-cmd2/cmd2/blob/master/examples/migrating.py)
    - A simple `cmd` application that you can migrate to `cmd2` by changing one line
- [modular_commands_basic.py](https://github.com/python-cmd2/cmd2/blob/master/examples/modular_commands_basic.py)
    - Demonstrates based `CommandSet` usage
- [modular_commands_dynamic.py](https://github.com/python-cmd2/cmd2/blob/master/examples/modular_commands_dynamic.py)
    - Demonstrates dynamic `CommandSet` loading and unloading
- [modular_commands_main.py](https://github.com/python-cmd2/cmd2/blob/master/examples/modular_commands_main.py)
    - Complex example demonstrating a variety of methods to load `CommandSets` using a mix of
      command decorators
- [modular_subcommands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/modular_subcommands.py)
    - Shows how to dynamically add and remove subcommands at runtime using `CommandSets`
- [override-parser.py](https://github.com/python-cmd2/cmd2/blob/master/examples/override_parser.py)
    - Shows how to override cmd2's default `Cmd2ArgumentParser` with your own customer parser class
- [paged_output.py](https://github.com/python-cmd2/cmd2/blob/master/examples/paged_output.py)
    - Shows how to use output pagination within `cmd2` apps via the `ppaged` method
- [persistent_history.py](https://github.com/python-cmd2/cmd2/blob/master/examples/persistent_history.py)
    - Shows how to enable persistent history in your `cmd2` application
- [pirate.py](https://github.com/python-cmd2/cmd2/blob/master/examples/pirate.py)
    - Demonstrates many features including colorized output, multiline commands, shorcuts,
      defaulting to shell, etc.
- [pretty_print.py](https://github.com/python-cmd2/cmd2/blob/master/examples/pretty_print.py)
    - Demonstrates use of cmd2.Cmd.ppretty() for pretty-printing arbitrary Python data structures
      like dictionaries.
- [python_scripting.py](https://github.com/python-cmd2/cmd2/blob/master/examples/python_scripting.py)
    - Shows how cmd2's built-in `run_pyscript` command can provide advanced Python scripting of cmd2
      applications
- [read_input.py](https://github.com/python-cmd2/cmd2/blob/master/examples/read_input.py)
    - Demonstrates the various ways to call `cmd2.Cmd.read_input()` for input history and tab
      completion
- [remove_builtin_commands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/remove_builtin_commands.py)
    - Shows how to remove any built-in cmd2 commands you do not want to be present in your cmd2
      application
- [remove_settable.py](https://github.com/python-cmd2/cmd2/blob/master/examples/remove_settable.py)
    - Shows how to remove any of the built-in cmd2 `Settables` you do not want in your cmd2
      application
- [subcommands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/subcommands.py)
    - Shows how to use `argparse` to easily support sub-commands within your cmd2 commands
- [table_creation.py](https://github.com/python-cmd2/cmd2/blob/master/examples/table_creation.py)
    - Contains various examples of using cmd2's table creation capabilities
- [tmux_launch.sh](https://github.com/python-cmd2/cmd2/blob/master/examples/tmux_launch.sh)
    - Shell script that launches two applications using tmux in different windows/tabs
- [tmux_split.sh](https://github.com/python-cmd2/cmd2/blob/master/examples/tmux_split.sh)
    - Shell script that launches two applications using tmux in a split pane view
- [unicode_commands.py](https://github.com/python-cmd2/cmd2/blob/master/examples/unicode_commands.py)
    - Shows that cmd2 supports unicode everywhere, including within command names
