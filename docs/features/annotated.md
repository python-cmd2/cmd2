# Annotated Argument Processing

!!! warning "Experimental"

    The `@with_annotated` decorator and its supporting `Argument` / `Option` metadata classes are
    **experimental**. The public API, the surface of accepted type annotations, and the generated
    argparse behavior may all change in future releases without a deprecation cycle. Pin a specific
    `cmd2` version if you depend on the exact current semantics, and expect to revisit your usage on
    upgrades.

    For production code that needs stable behavior, use
    [@with_argparser](argument_processing.md#with_argparser-decorator) instead.

The [@with_annotated][cmd2.annotated.with_annotated] decorator builds an argparse parser
automatically from the decorated function's type annotations. No manual `add_argument()` calls are
required, and the command body receives typed keyword arguments directly instead of an
`argparse.Namespace`.

The two decorators are interchangeable -- here is the same command written both ways:

=== "@with_annotated"

    ```py
    @with_annotated
    def do_greet(self, name: str, count: int = 1, loud: bool = False):
        for _ in range(count):
            msg = f"Hello {name}"
            self.poutput(msg.upper() if loud else msg)
    ```

=== "@with_argparser"

    ```py
    parser = Cmd2ArgumentParser()
    parser.add_argument('name', help='person to greet')
    parser.add_argument('--count', type=int, default=1, help='repetitions')
    parser.add_argument('--loud', action='store_true', help='shout')

    @with_argparser(parser)
    def do_greet(self, args):
        for _ in range(args.count):
            msg = f"Hello {args.name}"
            self.poutput(msg.upper() if args.loud else msg)
    ```

The annotated version is more concise, gives you typed parameters, and supports several advanced
cmd2 features directly, including `ns_provider`, `with_unknown_args`, and typed subcommands. Pick
`@with_argparser` when you need a stable, well-established API or fine-grained control over the
parser; pick `@with_annotated` when you want type-hint-driven ergonomics and can accept the
experimental status.

## Basic usage

Parameters without defaults become positional arguments. Parameters with defaults become `--option`
flags. Keyword-only parameters (after `*`) always become options, and without a default they become
required options.

Underscores in parameter names are converted to dashes in the generated flag, so `dry_run` becomes
`--dry-run`. The Python identifier you read inside the function body keeps its underscored form
(`args.dry_run`). To opt out, pass explicit names via `Option("--my_flag", ...)`.

```py
from cmd2.annotated import with_annotated

class MyApp(cmd2.Cmd):
    @with_annotated
    def do_greet(self, name: str, count: int = 1, loud: bool = False):
        """Greet someone."""
        for _ in range(count):
            msg = f"Hello {name}"
            self.poutput(msg.upper() if loud else msg)
```

The command `greet Alice --count 3 --loud` parses `name="Alice"`, `count=3`, `loud=True` and passes
them as keyword arguments.

## How annotations map to argparse

The decorator converts Python type annotations into `add_argument()` calls:

| Type annotation                        | Generated argparse setting                                 |
| -------------------------------------- | ---------------------------------------------------------- |
| `str`                                  | default (no `type=` needed)                                |
| `int`, `float`                         | `type=int` or `type=float`                                 |
| `bool` with a default                  | boolean optional flag via `BooleanOptionalAction`          |
| positional `bool`                      | parsed from `true/false`, `yes/no`, `on/off`, `1/0`        |
| `Path`                                 | `type=Path`                                                |
| `Enum` subclass                        | `type=converter`, `choices` from member values             |
| `decimal.Decimal`                      | `type=decimal.Decimal`                                     |
| `Literal[...]`                         | `type=literal-converter`, `choices` from values            |
| `list[T]` / `set[T]` / `tuple[T, ...]` | `nargs='+'` (or `'*'` if it has a default or is `\| None`) |
| `tuple[T, T]`                          | fixed `nargs=N` with `type=T`                              |
| `T \| None` (no default)               | positional with `nargs='?'` (accepts 0-or-1 tokens)        |
| `T \| None = None`                     | `--flag` option with `default=None`                        |

When collection types are used with `@with_annotated`, parsed values are passed to the command
function as:

- `list[T]` as `list`
- `set[T]` as `set`
- `tuple[T, ...]` as `tuple`

Unsupported patterns raise `TypeError`, including:

- unions with multiple non-`None` members such as `str | int`
- mixed-type tuples such as `tuple[int, str]`
- `Annotated[T, meta] | None`; write `Annotated[T | None, meta]` instead
- `Annotated[T, Argument(nargs=N)]` where `N` is `'*'`, `'+'`, or an integer `>= 1` and `T` is not a
  collection type. `nargs` values that produce a list of values need a collection annotation such as
  `list[T]` or `tuple[T, ...]`.
- `Annotated[tuple[T, T], Argument(nargs=N)]` where `N` differs from the number of elements declared
  by the tuple. The tuple type already pins `nargs`; user metadata cannot change it.

The parameter names `dest` and `subcommand` are reserved and may not be used as annotated parameter
names.

## Annotated metadata

For finer control, use `typing.Annotated` with [Argument][cmd2.annotated.Argument] or
[Option][cmd2.annotated.Option] metadata:

```py
from typing import Annotated
from cmd2.annotated import Argument, Option, with_annotated

class MyApp(cmd2.Cmd):
    def sport_choices(self) -> cmd2.Choices:
        return cmd2.Choices.from_values(["football", "basketball"])

    @with_annotated
    def do_play(
        self,
        sport: Annotated[str, Argument(
            choices_provider=sport_choices,
            help_text="Sport to play",
        )],
        venue: Annotated[str, Option(
            "--venue", "-v",
            help_text="Where to play",
            completer=cmd2.Cmd.path_complete,
        )] = "home",
    ):
        self.poutput(f"Playing {sport} at {venue}")
```

Both `Argument` and `Option` accept the same cmd2-specific fields as `add_argument()`: `choices`,
`choices_provider`, `completer`, `table_columns`, `suppress_tab_hint`, `metavar`, `nargs`, and
`help_text`.

`Option` additionally accepts `action`, `required`, and positional `*names` for custom flag strings
(e.g. `Option("--color", "-c")`).

When an `Option(action=...)` uses an argparse action that does not accept `type=` (`count`,
`store_true`, `store_false`, `store_const`, `help`, `version`), `@with_annotated` removes any
inferred `type` converter before calling `add_argument()`. This matches argparse behavior and avoids
parser-construction errors such as combining `action='count'` with `type=int`.

When a user-supplied `choices_provider` or `completer` overrides an inferred `Enum` or `Literal`,
the restrictive type converter is also dropped so the user-supplied values are not rejected at parse
time. The `Path` converter is permissive and is preserved when a custom completer is provided.

## Decorator options

`@with_annotated` currently supports:

- `ns_provider` -- prepopulate the namespace before parsing, mirroring `@with_argparser`
- `preserve_quotes` -- if `True`, quotes in arguments are preserved
- `with_unknown_args` -- if `True`, unrecognised arguments are passed as `_unknown`
- `subcommand_to` -- register the function as an annotated subcommand under a parent command
- `base_command` -- create a base command whose parser also adds subparsers and exposes
  `cmd2_handler`. A `cmd2_handler` parameter is only valid on a command decorated with
  `base_command=True`; declaring one elsewhere raises `TypeError`.
- `help` -- help text for an annotated subcommand
- `aliases` -- aliases for an annotated subcommand
- `groups` -- `Group` instances assigning parameter names to argument groups
- `mutually_exclusive_groups` -- `Group` instances of mutually exclusive parameters
- `description` -- parser description shown in `--help`
- `epilog` -- parser epilog shown at the end of `--help`
- `formatter_class` -- a custom help formatter class for the parser
- `parser_class` -- a custom parser class (defaults to the configured default)

```py
@with_annotated(with_unknown_args=True)
def do_rawish(self, name: str, _unknown: list[str] | None = None):
    self.poutput((name, _unknown))
```

## Parser customization

`description`, `epilog`, `formatter_class`, and `parser_class` are passed through to the generated
parser. Argument groups are declared with [Group][cmd2.annotated.Group]; pass `title` and
`description` for a titled help section (omit them for an untitled group):

```py
from cmd2.annotated import Group, with_annotated

class App(cmd2.Cmd):
    @with_annotated(
        description="Open a network connection.",
        epilog="Example: connect example.com --port 2222",
        groups=(Group("host", "port", title="connection", description="where to connect"),),
    )
    def do_connect(self, host: str, port: int = 22, verbose: bool = False):
        self.poutput(f"connecting to {host}:{port}")
```

`mutually_exclusive_groups` also takes `Group` instances (their `title`/`description` are ignored,
since argparse mutually-exclusive groups have no header).

## Annotated subcommands

`@with_annotated` can also build typed subcommand trees without manually constructing subparsers.

```py
@with_annotated(base_command=True)
def do_manage(self, *, cmd2_handler):
    handler = cmd2_handler
    if handler:
        handler()

@with_annotated(subcommand_to="manage", help="list projects")
def manage_list(self):
    self.poutput("listing")
```

For nested subcommands, `subcommand_to` can be space-delimited, for example
`subcommand_to="manage project"`. The intermediate level must also be declared as a subcommand that
creates its own subparsers:

```py
@with_annotated(subcommand_to="manage", base_command=True, help="manage projects")
def manage_project(self, *, cmd2_handler):
    handler = cmd2_handler
    if handler:
        handler()

@with_annotated(subcommand_to="manage project", help="add a project")
def manage_project_add(self, name: str):
    self.poutput(f"added {name}")
```

## Lower-level parser building

[cmd2.annotated.build_parser_from_function][cmd2.annotated.build_parser_from_function] builds the
parser directly from a function without registering a command. It accepts the same `groups`,
`mutually_exclusive_groups`, `description`, `epilog`, `formatter_class`, and `parser_class`
arguments as `@with_annotated`.

```py
@with_annotated(preserve_quotes=True)
def do_raw(self, text: str):
    self.poutput(f"raw: {text}")
```

## Automatic completion from types

With `@with_annotated`, arguments annotated as `Path` or `Enum` get automatic completion without
needing an explicit `choices_provider` or `completer`.

Specifically:

- `Path` (or any `Path` subclass) triggers filesystem path completion
- `MyEnum` (any `enum.Enum` subclass) triggers completion from enum member values

With `@with_argparser`, provide `choices`, `choices_provider`, or `completer` explicitly when you
want completion behavior.

## Stability and feedback

Because this feature is experimental:

- Behavior of edge cases (mixed-type tuples, deeply-nested `Annotated`, conflicting metadata) may
  change.
- Diagnostic error messages may be reworded.
- The set of supported type annotations may be expanded or trimmed.

If you depend on `@with_annotated`, please share feedback and edge cases via the
[issue tracker](https://github.com/python-cmd2/cmd2/issues) so behavior can be locked in before the
feature graduates out of experimental.
