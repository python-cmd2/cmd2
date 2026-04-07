# Help

From our experience, end users rarely read documentation no matter how high-quality or useful that
documentation might be. So it is important that you provide good built-in help within your
application. Fortunately, `cmd2` makes this easy.

## Getting Help

`cmd2` makes it easy for end users of `cmd2` applications to get help via the built-in `help`
command. The `help` command by itself displays a list of the commands available:

```text
(Cmd) help

Documented Commands
───────────────────
alias  help     ipy    py    run_pyscript  set    shortcuts
edit   history  macro  quit  run_script    shell
```

The `help` command can also be used to provide detailed help for a specific command:

```text
(Cmd) help quit
Usage: quit [-h]

Exit this application.

Optional Arguments:
  -h, --help  show this help message and exit
```

## Providing Help

`cmd2` makes it easy for developers of `cmd2` applications to provide this help. By default, the
help for a command is the docstring for the `do_*` method defining the command - e.g. for a command
**foo**, that command is implemented by defining the `do_foo` method and the docstring for that
method is the help.

For commands which use the [@with_argparser][cmd2.with_argparser] decorator to parse arguments, help
is provided by `argparse`. See [Help Messages](./argument_processing.md#help-messages) for more
information.

Occasionally there might be an unusual circumstance where providing static help text isn't good
enough and you want to provide dynamic information in the help text for a command. To meet this
need, if a `help_foo` method is defined to match the `do_foo` method, then that method will be used
to provide the help for command **foo**. This dynamic help is only supported for commands which do
not use an `argparse` decorator because we didn't want different output for `help cmd` than for
`cmd -h`.

## Categorizing Commands

In `cmd2`, the `help` command organizes its output into categories. Every command belongs to a
category, and the display is driven by the `DEFAULT_CATEGORY` class variable.

There are 3 methods of specifying command categories:

1. Using the `DEFAULT_CATEGORY` class variable (Automatic)
1. Using the [@with_category][cmd2.with_category] decorator (Manual)
1. Using the [categorize()][cmd2.categorize] function (Manual)

### Automatic Categorization

The most efficient way to categorize commands is by defining the `DEFAULT_CATEGORY` class variable
in your `Cmd` or `CommandSet` class. Any command defined in that class that does not have an
explicit category override will automatically be placed in this category.

By default, `cmd2.Cmd` defines its `DEFAULT_CATEGORY` as `"Cmd2 Commands"`.

```py
class MyApp(cmd2.Cmd):
    # All commands defined in this class will be grouped here
    DEFAULT_CATEGORY = 'Application Commands'

    def do_echo(self, arg):
        """Echo command"""
        self.poutput(arg)
```

This also works for [Command Sets](./modular_commands.md):

```py
class Plugin(cmd2.CommandSet):
    DEFAULT_CATEGORY = 'Plugin Commands'

    def do_plugin_cmd(self, _):
        """Plugin command"""
        self._cmd.poutput('Plugin')
```

When using inheritance, `cmd2` uses the `DEFAULT_CATEGORY` of the class where the command was
actually defined. This means built-in commands (like `help`, `history`, and `quit`) stay in the
`"Cmd2 Commands"` category, while your commands move to your custom category.

If you want to rename the built-in category itself, you can do so by reassigning
`cmd2.Cmd.DEFAULT_CATEGORY` at the class level within your `Cmd` subclass:

```py
class MyApp(cmd2.Cmd):
    # Rename the framework's built-in category
    cmd2.Cmd.DEFAULT_CATEGORY = 'Shell Commands'

    # Set the category for your own commands
    DEFAULT_CATEGORY = 'Application Commands'
```

For a complete demonstration of this functionality, see the
[default_categories.py](https://github.com/python-cmd2/cmd2/blob/main/examples/default_categories.py)
example.

### Manual Categorization

If you need to move an individual command to a different category than the class default, you can
use the `@with_category` decorator or the `categorize()` function. These manual settings always take
precedence over the `DEFAULT_CATEGORY`.

Using the `@with_category` decorator:

```py
@with_category('Connecting')
def do_which(self, _):
    """Which command"""
    self.poutput('Which')
```

Using the `categorize()` function:

You can call with a single function:

```py
def do_connect(self, _):
    """Connect command"""
    self.poutput('Connect')

# Tag the above command functions under the category Connecting
categorize(do_connect, CMD_CAT_CONNECTING)
```

Or with an Iterable container of functions:

```py
def do_undeploy(self, _):
    """Undeploy command"""
    self.poutput('Undeploy')

def do_stop(self, _):
    """Stop command"""
    self.poutput('Stop')

def do_findleakers(self, _):
    """Find Leakers command"""
    self.poutput('Find Leakers')

# Tag the above command functions under the category Application Management
categorize((do_undeploy,
            do_stop,
            do_findleakers), CMD_CAT_APP_MGMT)
```

The `help` command also has a verbose option (`help -v` or `help --verbose`) that combines the help
categories with per-command help messages:

    Application Management
    ─────────────────────────────────────
    Name          Description
    ─────────────────────────────────────
    deploy        Deploy command.
    expire        Expire command.
    findleakers   Find Leakers command.
    list          List command.
    redeploy      Redeploy command.
    restart       Restart command.
    sessions      Sessions command.
    start         Start command.
    stop          Stop command.
    undeploy      Undeploy command.


    Command Management
    ─────────────────────────────────────────────────────────────────
    Name               Description
    ─────────────────────────────────────────────────────────────────
    disable_commands   Disable the Application Management commands.
    enable_commands    Enable the Application Management commands.


    Connecting
    ────────────────────────────
    Name      Description
    ────────────────────────────
    connect   Connect command.
    which     Which command.


    Server Information
    ─────────────────────────────────────────────────────────────────────────────────────────────────
    Name                  Description
    ─────────────────────────────────────────────────────────────────────────────────────────────────
    resources             Resources command.
    serverinfo            Server Info command.
    sslconnectorciphers   SSL Connector Ciphers command is an example of a command that contains
                        multiple lines of help information for the user. Each line of help in a
                        contiguous set of lines will be printed and aligned in the verbose output
                        provided with 'help --verbose'.
    status                Status command.
    thread_dump           Thread Dump command.
    vminfo                VM Info command.


    Other
    ─────────────────────────────────────────────────────────────────────────────────────────
    Name           Description
    ─────────────────────────────────────────────────────────────────────────────────────────
    alias          Manage aliases.
    config         Config command.
    edit           Run a text editor and optionally open a file with it.
    help           List available commands or provide detailed help for a specific command.
    history        View, run, edit, save, or clear previously entered commands.
    macro          Manage macros.
    quit           Exit this application.
    run_pyscript   Run Python script within this application's environment.
    run_script     Run text script.
    set            Set a settable parameter or show current settings of parameters.
    shell          Execute a command as if at the OS prompt.
    shortcuts      List available shortcuts.
    version        Version command.

When called with the `-v` flag for verbose help, the one-line description for each command is
provided by the first line of the docstring for that command's associated `do_*` method.
