# Typer Support

cmd2 can optionally use [Typer](https://typer.tiangolo.com/) (built on
[Click](https://click.palletsprojects.com/)) to parse command arguments from type annotations
instead of `argparse`. This is an alternative to [@with_argparser][cmd2.with_argparser] for
developers who prefer annotation-driven CLI definitions.

## Installation

```bash
pip install -U cmd2[typer]
```

## Basic Usage

Use the `@cmd2.with_typer` decorator and type annotations to define arguments.

```py
from typing import Annotated
import typer
import cmd2


class App(cmd2.Cmd):
    @cmd2.with_typer
    def do_greet(
        self,
        name: Annotated[str, typer.Argument(help="Name to greet")],
        times: Annotated[int, typer.Option("--times", min=1, help="Number of greetings")] = 1,
    ) -> None:
        for _ in range(times):
            self.poutput(f"Hello, {name}")
```

cmd2 inspects the decorated method, builds a Typer command from its signature, and uses that command
for parsing, help, and tab completion. The `self` parameter is handled automatically.

### `preserve_quotes`

By default, cmd2 strips quotes from user input before passing it to the parser. If your command
needs to receive the raw quoted strings, pass `preserve_quotes=True`.

```py
@cmd2.with_typer(preserve_quotes=True)
def do_raw(self, text: Annotated[str, typer.Argument()]) -> None:
    self.poutput(text)  # input: raw "hello" -> output: "hello"
```

This behaves the same as `preserve_quotes` on `@with_argparser`.

### Error Handling

Parse errors from Typer/Click are caught and displayed to the user without exiting the REPL. For
example, if a required argument is missing, the user sees the Click error message and remains at the
prompt.

## Subcommands

For commands with subcommands, build a `typer.Typer()` app and pass it to `@cmd2.with_typer(...)`.

```py
from typing import Annotated
import typer
import cmd2


class AdminCommands(cmd2.CommandSet):
    base_command = typer.Typer(help="Base command help")
    users_command = typer.Typer(help="User management commands")

    @base_command.command("show")
    def base_show(
        self,
        verbose: Annotated[bool, typer.Option("--verbose")] = False,
    ) -> None:
        self._cmd.poutput(f"verbose={verbose}")

    @users_command.command("add")
    def users_add(
        self,
        name: Annotated[str, typer.Argument(help="User name")],
        admin: Annotated[bool, typer.Option("--admin")] = False,
    ) -> None:
        self._cmd.poutput(f"added {name}, admin={admin}")

    base_command.add_typer(users_command, name="users")

    @cmd2.with_typer(base_command)
    def do_manage(self) -> None:
        """Entry point for the Typer app."""
        pass
```

That produces a cmd2 command tree like this:

- `manage show --verbose`
- `manage users add alice --admin`

!!! note

    This example uses a [CommandSet][cmd2.CommandSet], which is cmd2's mechanism for organizing
    commands into reusable groups (see [Modular Commands](modular_commands.md)). Inside a
    `CommandSet`, use `self._cmd` to access the `Cmd` instance (e.g. `self._cmd.poutput()`).
    You can also define Typer commands directly on a `Cmd` subclass, where `self` is the
    `Cmd` instance and you call `self.poutput()` directly.

### What `add_typer()` Does

This line:

```py
base_app.add_typer(users_app, name="users")
```

mounts one Typer app under another. In this case:

- `base_app` is the root command tree for `manage`
- `users_app` becomes a nested subcommand group named `users`

That is why `add` is invoked through `users` instead of directly under `manage`:

- `@base_app.command("show")` becomes `manage show`
- `@users_app.command("add")` becomes `manage users add`

Without `add_typer()`, the nested Typer app is not attached to the command tree and its commands are
not reachable from cmd2.

### How It Works

There are two supported patterns:

- **`@cmd2.with_typer`** (no arguments) cmd2 creates a one-command Typer app from the method
  signature. Use this for simple commands.
- **`@cmd2.with_typer(existing_typer_app)`** (explicit Typer app) cmd2 uses the Typer app you built.
  Use this when you need subcommands or want explicit control over the Typer command tree.

For explicit Typer apps, the decorated `do_*` method is only the cmd2 entry point. The real command
handlers are the callbacks registered on the Typer app. Those callbacks can live on either a `Cmd`
or a `CommandSet`, but they should still take `self` as their first argument so cmd2 can bind them
to the active instance at runtime.

### Running the Base Command

When you pass an explicit Typer app to `@cmd2.with_typer(...)`, the cmd2 `do_*` method provides the
command name, but Typer controls what happens after that.

For the example above:

- `manage show` runs the `show` command
- `manage users add alice` runs the nested `add` command inside the `users` group
- `manage` (with no subcommand) shows help or usage information by default

If you want bare `manage` to perform some action, define a callback on the Typer app itself. If you
want it to act only as a container for subcommands, leave the root without business logic and let
Typer show help or usage text.

### Help and Completion

Subcommands integrate with cmd2 help and completion:

- `help manage` shows the top-level Typer help
- `help manage users add` shows nested subcommand help
- Tab completion works for subcommand names, options, and Typer `autocompletion` callbacks

## When To Use Typer vs argparse

**Use Typer** when:

- you want type-annotation-driven parsing
- you already have Typer models or Click-style completion callbacks
- you want to define nested subcommands with a Typer app

**Use `argparse`** (`@with_argparser`) when:

- you need cmd2 features that are specific to `with_argparser`, such as `ns_provider` or
  `with_unknown_args`
- your application already has substantial argparse parser customizations
- you want `cmd2`'s rich-argparse help formatting (Typer uses Click's own help formatter)

## Notes

- `help <command>` uses Click's help output for Typer-based commands, not argparse help.
- Parse errors use Click's error formatting and are caught so they do not exit the REPL.
- Completion for Typer-based commands is provided by Click's `shell_complete` API.
- Typer support is optional and requires installing the `typer` extra.

See the [typer_example](https://github.com/python-cmd2/cmd2/blob/main/examples/typer_example.py) for
a working application that demonstrates all of these features.
