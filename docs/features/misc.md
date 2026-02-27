# Miscellaneous Features

## Timer {: #Timer }

Turn the timer setting on, and `cmd2` will show the wall time it takes for each command to execute.

## Exiting

Like many shell applications, `cmd2` applications can be exited by pressing `Ctrl-D` on an empty
line, or by executing the `quit` command.

## select

Presents numbered options to user, as bash `select`.

`app.select` is called from within a method (not by the user directly; it is `app.select`, not
`app.do_select`).

::: cmd2.Cmd.select

```py
def do_eat(self, arg):
    sauce = self.select('sweet salty', 'Sauce? ')
    result = '{food} with {sauce} sauce, yum!'
    result = result.format(food=arg, sauce=sauce)
    self.stdout.write(result + '\n')
```

```text
(Cmd) eat wheaties
    1. sweet
    2. salty
Sauce? 2
wheaties with salty sauce, yum!
```

## Disabling Commands

`cmd2` supports disabling commands during runtime. This is useful if certain commands should only be
available when the application is in a specific state. When a command is disabled, it will not show
up in the help menu or tab complete. If a user tries to run the command, a command-specific message
supplied by the developer will be printed. The following functions support this feature.

- [enable_command][cmd2.Cmd.enable_command] : Enable an individual command
- [enable_category][cmd2.Cmd.enable_category] : Enable an entire category of commands
- [disable_command][cmd2.Cmd.disable_command] : Disable an individual command and set the message
  that will print when this command is run or help is called on it while disabled
- [disable_category][cmd2.Cmd.disable_category] : Disable an entire category of commands and set the
  message that will print when anything in this category is run or help is called on it while
  disabled

See the definitions of these functions for descriptions of their arguments.

See the `do_enable_commands()` and `do_disable_commands()` functions in the
[help_categories.py](https://github.com/python-cmd2/cmd2/blob/main/examples/help_categories.py)
example for a demonstration.
