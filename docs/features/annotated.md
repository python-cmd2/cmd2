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
- an optional fixed-arity positional, such as `Annotated[tuple[int, int], Argument()] = (1, 2)`,
  `Annotated[tuple[int, int] | None, Argument()]`, or any positional `Argument(nargs=N)` with a
  default or `| None`. argparse cannot make a fixed-arity positional optional (there is no `nargs`
  for "absent or exactly `N` tokens"), so use a variable-arity type like `tuple[T, ...]`, drop the
  default, or make it an option (give it a default without `Argument()`).
- `Annotated[tuple[T, T], Argument(nargs=N)]` where `N` differs from the number of elements declared
  by the tuple. The tuple type already pins `nargs`; user metadata cannot change it.

The parameter names `dest` and `subcommand` are reserved and may not be used as annotated parameter
names. `cmd2_statement` receives the parsed [cmd2.Statement][] object, and `cmd2_handler` (only on a
command decorated with `@with_annotated(base_command=True)`) receives the subcommand handler.

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

When an `Option(action=...)` uses a zero-argument argparse action that takes no value from the
command line (`count`, `store_true`, `store_false`, `store_const`, `append_const`),
`@with_annotated` removes the value-oriented metadata inferred from the type before calling
`add_argument()`: the `type` converter, the static `choices`, and any inferred tab-completer (such
as the path completer for `Path`) or `choices_provider`. This matches argparse behavior (which
rejects a completer on a value-less action) and avoids parser-construction errors such as combining
`action='count'` with `type=int`. Actions that do consume values (`append` / `extend` on a
`list[T]`, or a plain value option) keep the inferred converter and completer. `action='help'` and
`action='version'` are not supported.

Pairing `const` with an explicit `nargs` on a scalar `Option` selects argparse's optional-value
idiom instead of `store_const`. `Annotated[str | None, Option("--log", nargs='?', const="CONSOLE")]`
keeps the `store` action and the inferred `type` converter, so the flag is three-way: absent yields
the default, a bare `--log` yields the `const`, and `--log VALUE` yields the converted `VALUE`. The
`const` is stored verbatim (it is not run through the converter), so it must already match the
declared type. Without an explicit `nargs`, `const` alone still infers the value-less `store_const`
(present yields the `const`, and supplying a value is an error).

`Option(action=...)` also accepts a custom `argparse.Action` subclass. The class is passed straight
through to `add_argument()` and owns storage of the parsed value, so the type-inferred collection
casting and the action-specific type/const/shape constraints are skipped; the inferred `type=`
converter, default, and `required` are still applied so the class receives them like any hand-built
`add_argument()` call.

```py
class UpperAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values.upper())

@with_annotated
def do_shout(self, name: Annotated[str, Option("--name", action=UpperAction)] = ""):
    self.poutput(name)
```

`action='help'` and `action='version'` are not supported by `@with_annotated`; use `@with_argparser`
if you need them.

`Argument()` and `Option()` refuse a handful of `add_argument()` kwargs that the decorator derives
from the function signature itself, so misusing them surfaces as a clear `TypeError` instead of a
silent override. The refused kwargs are:

- `type` -- comes from the parameter annotation
- `dest` -- comes from the parameter name
- `action` and `required` on `Argument` -- only `Option` accepts them; positional arguments have no
  action and are required unless they carry a default or `| None`

Every other `add_argument()` parameter passes through, including any custom parameter registered via
[register_argparse_argument_parameter][cmd2.argparse_utils.register_argparse_argument_parameter].

A `default` may be supplied either through the function signature or as a metadata kwarg. The two
forms are equivalent:

```py
# Signature default
def do_x(self, name: Annotated[str, Option("--name")] = "HI"): ...

# Metadata default (same behaviour)
def do_x(self, name: Annotated[str, Option("--name", default="HI")]): ...
```

Specifying both at the same time is a conflict and raises `TypeError`. `argparse.SUPPRESS` is
rejected as a default from either source, because suppressing the namespace attribute would call the
function without the keyword argument it expects.

Parser-construction kwargs such as `add_help`, `prefix_chars`, `fromfile_prefix_chars`,
`argument_default`, `conflict_handler`, and `allow_abbrev` are not exposed by `@with_annotated`. Set
them on a custom `parser_class` subclass and pass it via `parser_class=`.

When a user-supplied `choices_provider` or `completer` is given for an inferred `Enum` or `Literal`,
the inferred static `choices` list is dropped so completion is driven by the provider or completer.
The inferred `type` converter is preserved, so parsed values still coerce to the declared type
(`Literal[1, 2]` yields an `int`, an `Enum` yields its member) and values outside the type are
rejected at parse time.

An explicit `choices=` is reconciled with the inferred type rather than fighting it:

- The values are run through the inferred `type` converter so they match argparse's post-conversion
  comparison. `Annotated[int, Option("--n", choices=["1", "2"])]` is normalized to `choices=[1, 2]`,
  so `--n 1` is accepted. A choice the converter rejects (`choices=["1", "nope"]` on an `int`) is a
  build-time `TypeError`. Values already of the declared type are left as-is.
- An explicit `choices=` takes precedence over a _type-inferred_ completer (such as the `Path`
  completer): the choices are kept (so they validate and drive completion) and the inferred
  completer is dropped. A `choices_provider`/`completer` you pass yourself still wins over
  `choices=`.

An `Enum` parameter accepts both member **values** and member **names** on the command line
(`Color.RED` with value `"red"` is selected by either `red` or `RED`); tab-completion and `--help`
list the values.

## Decorator options

`@with_annotated` currently supports:

- `ns_provider` -- prepopulate the namespace before parsing, mirroring `@with_argparser`
- `preserve_quotes` -- if `True`, quotes in arguments are preserved
- `with_unknown_args` -- if `True`, unrecognised arguments are passed as `_unknown`
- `subcommand_to` -- register the function as an annotated subcommand under a parent command
- `base_command` -- create a base command whose parser also adds subparsers and exposes
  `cmd2_handler`. A `cmd2_handler` parameter is only valid on a command decorated with
  `base_command=True`; declaring one elsewhere raises `TypeError`.
- `subcommand_required` -- whether a subcommand must be supplied (only with `base_command=True`,
  default `True`)
- `subcommand_metavar` -- metavar shown for the subcommands group (only with `base_command=True`,
  default `"SUBCOMMAND"`)
- `subcommand_title` -- title for the subcommands `--help` section (only with `base_command=True`)
- `subcommand_description` -- description for the subcommands `--help` section (only with
  `base_command=True`)
- `help` -- help text for an annotated subcommand (only valid with `subcommand_to`)
- `aliases` -- aliases for an annotated subcommand (only valid with `subcommand_to`)
- `deprecated` -- mark the subcommand as deprecated in `--help` (only valid with `subcommand_to`)
- `groups` -- `Group` instances assigning parameter names to argument groups
- `mutually_exclusive_groups` -- `Group` instances of mutually exclusive parameters
- `parser_class` -- a custom parser class (defaults to the configured default)
- `**parser_kwargs` -- every other parser-construction kwarg accepted by `Cmd2ArgumentParser` is
  forwarded through PEP 692
  [`Unpack`][typing.Unpack][`[Cmd2ParserKwargs]`][cmd2.annotated.Cmd2ParserKwargs]: `description`,
  `epilog`, `prog`, `usage`, `parents`, `argument_default`, `prefix_chars`, `fromfile_prefix_chars`,
  `conflict_handler`, `add_help`, `allow_abbrev`, `exit_on_error`, `formatter_class`,
  `ap_completer_type`, and on Python &ge; 3.14 `suggest_on_error` / `color`. Two behaviors layer on
  top of the raw passthrough:
    - `description` -- when omitted, the first paragraph of the function's docstring (up to the
      first blank line) is used; pass an explicit value to override.
    - `prog` -- rejected when `subcommand_to` is set; cmd2's subcommand machinery rewrites `prog`
      from the parent command hierarchy and any value here would be silently overwritten.

```py
@with_annotated(with_unknown_args=True)
def do_rawish(self, name: str, _unknown: list[str] | None = None):
    self.poutput((name, _unknown))
```

## Parser customization

Every `Cmd2ArgumentParser` constructor kwarg flows straight through `@with_annotated` and
`build_parser_from_function` via PEP 692
[`Unpack[Cmd2ParserKwargs]`][cmd2.annotated.Cmd2ParserKwargs]. The
[`Cmd2ParserKwargs`][cmd2.annotated.Cmd2ParserKwargs] `TypedDict` is the single source of truth for
the forwarded kwargs and gives type-checkers/IDEs autocomplete on the decorator's call site: adding
a new ctor kwarg to `Cmd2ArgumentParser` only needs a matching field on `Cmd2ParserKwargs`, and the
annotated decorator picks it up automatically.

`parser_class` stays as its own explicit kwarg because it selects the class itself rather than a
value passed to it. Argument groups are declared with [Group][cmd2.annotated.Group]; pass `title`
and `description` for a titled help section (omit them for an untitled group):

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

If you omit `description`, the first paragraph of the function's docstring (everything up to the
first blank line) is used as the parser description; subsequent paragraphs are dropped so rst field
directives like `:param name:` don't leak into `--help`. Pass `description=""` to suppress the
automatic fill, or `description="..."` to override it.

```py
@with_annotated
def do_greet(self, name: str):
    """Greet someone by name.

    :param name: who to greet
    """
    self.poutput(f"hello {name}")
# parser.description == "Greet someone by name."
```

`mutually_exclusive_groups` also takes `Group` instances (their `title`/`description` are ignored,
since argparse mutually-exclusive groups have no header). Pass `Group(..., required=True)` to make
the mutex group itself required -- argparse will then enforce that exactly one of its members must
be supplied. `required=True` is rejected on a plain (non-mutex) `Group` because `add_argument_group`
has no `required` flag.

```py
@with_annotated(
    mutually_exclusive_groups=(Group("verbose", "quiet", required=True),),
)
def do_run(self, verbose: bool = False, quiet: bool = False): ...
```

`parents=` mirrors argparse's standard parents mechanism for sharing argument definitions across
parsers. `argument_default=argparse.SUPPRESS` is accepted only when no argument could be stranded by
it: it removes an absent argument from the parsed namespace, which is safe for an argument that is
always supplied (a required option, a mandatory positional) or that carries its own default, but not
for an _omittable_ argument with no default (for example a `T | None` positional, which becomes
`nargs='?'`). If any such argument is present, `@with_annotated` raises `TypeError` rather than let
the function be called missing a keyword argument it expects (mirroring the per-argument
`default=argparse.SUPPRESS` rejection). `*args` is exempt, since the invocation path substitutes an
empty tuple for it.

The remaining argparse kwargs cover less-common needs but are wired through unchanged:

- `prefix_chars="+-"` accepts options that start with `+` (e.g. `+verbose`); pair with an explicit
  `Option("+verbose")` to declare such flags.
- `fromfile_prefix_chars="@"` lets a user write `mycmd @args.txt` and have the file's contents
  spliced in as arguments.
- `conflict_handler="resolve"` lets a parent parser's option be redefined locally without an error
  -- useful with `parents=` when you want to override an inherited flag.
- `add_help=False` drops the auto-added `-h`/`--help` action (cmd2's standard parser keeps it on by
  default).
- `allow_abbrev=False` requires users to type the full long-option name (no `--verb` for
  `--verbose`).
- `exit_on_error=False` makes parse failures raise `argparse.ArgumentError` instead of calling
  `sys.exit`; useful when embedding the parser inside another flow.

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
`mutually_exclusive_groups`, `parser_class`, and forwarded
[`Unpack[Cmd2ParserKwargs]`][cmd2.annotated.Cmd2ParserKwargs] as `@with_annotated`.

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
