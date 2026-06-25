# Annotated Argument Processing

!!! warning "Experimental"

    The `@with_annotated` decorator and its supporting `Argument` / `Option` metadata classes are
    **experimental**. The public API, the surface of accepted type annotations, and the generated
    argparse behavior may all change in future releases without a deprecation cycle. Pin a specific
    `cmd2` version if you depend on the exact current semantics, and expect to revisit your usage on
    upgrades.

    For production code that needs stable behavior, use
    [@with_argparser](argument_processing.md#with_argparser-decorator) instead.

The [@with_annotated][cmd2.with_annotated] decorator builds an argparse parser automatically from
the decorated function's type annotations. No manual `add_argument()` calls are required, and the
command body receives typed keyword arguments directly instead of an `argparse.Namespace`.

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

| Type annotation                                         | Generated argparse setting                                 |
| ------------------------------------------------------- | ---------------------------------------------------------- |
| `str`                                                   | default (no `type=` needed)                                |
| `int`, `float`                                          | `type=int` or `type=float`                                 |
| `bool` with a default                                   | boolean optional flag via `BooleanOptionalAction`          |
| positional `bool`                                       | parsed from `true/false`, `yes/no`, `on/off`, `1/0`        |
| `Path`                                                  | `type=Path`                                                |
| `Enum` subclass                                         | `type=converter`, `choices` from member values             |
| `EnumA \| EnumB` (all members `Enum`)                   | first member to accept a token wins; `choices` merged      |
| `decimal.Decimal`                                       | `type=decimal.Decimal`                                     |
| `Literal[...]`                                          | `type=literal-converter`, `choices` from values            |
| `list[T]` / `set[T]` / `frozenset[T]` / `tuple[T, ...]` | `nargs='+'` (or `'*'` if it has a default or is `\| None`) |
| `tuple[T, T]`                                           | fixed `nargs=N` with `type=T`                              |
| `T \| None` (no default)                                | positional with `nargs='?'` (accepts 0-or-1 tokens)        |
| `T \| None = None`                                      | `--flag` option with `default=None`                        |

When collection types are used with `@with_annotated`, parsed values are passed to the command
function as:

- `list[T]` as `list`
- `set[T]` as `set`
- `frozenset[T]` as `frozenset`
- `tuple[T, ...]` as `tuple`

Unsupported patterns raise `TypeError`, including:

- unions with multiple non-`None` members such as `str | int`, unless every member is an `Enum`
  subclass (e.g. `EnumA | EnumB`), which resolves by trying each member's converter in order
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
names. `cmd2_statement` receives the parsed [cmd2.Statement][] object, and `cmd2_subcommand_func`
(only on a command decorated with `@with_annotated(base_command=True)`) receives the subcommand
handler.

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
`help_text`. They also accept `converter` / `preprocess` for
[custom conversion](#custom-conversion-converter-and-preprocess) and `allow_unknown_entry` for
[enum aliases](#enum-aliases-and-special-keywords-allow_unknown_entry).

`Option` additionally accepts `action`, `required`, and positional `*names` for custom flag strings
(e.g. `Option("--color", "-c")`).

### Enum aliases and special keywords (`allow_unknown_entry`)

By default an `Enum` parameter accepts only member values and member names. To let an enum also
accept aliases, alternate spellings, or special keywords, define the standard Python
[`_missing_`](https://docs.python.org/3/library/enum.html#enum.Enum._missing_) hook on the enum and
opt in with `allow_unknown_entry=True`:

```py
import enum
from typing import Annotated
from cmd2.annotated import Argument, with_annotated

class Color(enum.Enum):
    red = "red"
    green = "green"
    blue = "blue"

    @classmethod
    def _missing_(cls, value):
        # map a special keyword onto a real member; return None to reject
        return cls.red if str(value).lower() == "auto" else None

class MyApp(cmd2.Cmd):
    @with_annotated
    def do_theme(self, choice: Annotated[Color, Argument(allow_unknown_entry=True)]) -> None:
        self.poutput(f"theme set to {choice.value}")
```

`theme auto` now resolves through `_missing_` to `Color.red`, while `theme red` (value) and
`theme green` (name) keep working as before. A token that `_missing_` declines (returns `None`) is
still rejected with the usual "choose from ..." error. Any exception `_missing_` itself raises
propagates as-is (it is not masked as an "invalid choice"). The flag has no effect on non-`Enum`
annotations, and an `Enum` that does not override `_missing_` inherits the default (which returns
`None`), so the flag is simply inert for it. It also applies when the enum is a collection element
(e.g. `Annotated[list[Color], Argument(allow_unknown_entry=True)]`).

Because `_missing_` aliases are dynamic, they are not added to the advertised `choices`, so they do
not appear in `--help` or tab-completion; the canonical member values remain the listed choice set.

### Unions of Enums

A parameter annotated as a union whose members are all `Enum` subclasses (e.g. `EnumA | EnumB`) is
accepted. Each member keeps its own converter, and a token is resolved by the **first member that
accepts it**:

```py
@with_annotated
def do_pick(self, choice: Suit | Rank) -> None:
    if isinstance(choice, Suit):
        self.poutput(f"suit {choice.name}")
    else:
        self.poutput(f"rank {choice.name}")
```

Because resolution is first-match-wins, **order matters**: if a token is a valid value (or name) for
more than one member, the member listed first in the union wins, and the later member's identical
token becomes unreachable. `allow_unknown_entry` and each member's `_missing_` hook still apply per
member; a member whose `_missing_` _raises_ on a token (rather than returning `None`) simply
declines it, so the next member is still tried and the raise does not abort the whole union. Only
when every member declines is the usual "choose from ..." error raised. Only `Enum` members are
supported; a union containing a `Literal` or any non-`Enum` type is still rejected as ambiguous.

When the two value sets overlap, prefer [typed subcommands](#annotated-subcommands) (one `Enum` per
subcommand) so the choice is explicit and collision-free.

### Actions

When an `Option(action=...)` uses a zero-argument argparse action that takes no value from the
command line (`count`, `store_true`, `store_false`, `store_const`, `append_const`),
`@with_annotated` strips the value-oriented metadata it inferred from the type before calling
`add_argument()`:

- the `type` converter,
- the static `choices`, and
- any inferred tab-completer (such as the path completer for `Path`) or `choices_provider`.

This matches argparse behavior (which rejects a completer on a value-less action) and avoids
parser-construction errors such as combining `action='count'` with `type=int`. Actions that _do_
consume values (`append` / `extend` on a `list[T]`, or a plain value option) keep the inferred
converter and completer.

Pairing `const` with an explicit `nargs` on a scalar `Option` selects argparse's optional-value
idiom instead of `store_const`. `Annotated[str | None, Option("--log", nargs='?', const="CONSOLE")]`
keeps the `store` action and the inferred `type` converter, so the flag is three-way:

- absent yields the default,
- a bare `--log` yields the `const`, and
- `--log VALUE` yields the converted `VALUE`.

The `const` is stored verbatim (it is not run through the converter), so it must already match the
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

### Reserved keyword arguments

`Argument()` and `Option()` refuse a handful of `add_argument()` kwargs that the decorator derives
from the function signature itself, so misusing them surfaces as a clear `TypeError` instead of a
silent override. The refused kwargs are:

- `type` -- comes from the parameter annotation; for a custom string-to-value callable use
  [`converter`](#custom-conversion-converter-and-preprocess) (or `preprocess` to transform the token
  first)
- `dest` -- comes from the parameter name
- `action` and `required` on `Argument` -- only `Option` accepts them; positional arguments have no
  action and are required unless they carry a default or `| None`

Every other `add_argument()` parameter passes through, including any custom parameter registered via
[register_argparse_argument_parameter][cmd2.argparse_utils.register_argparse_argument_parameter].

### Defaults

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

### Choices and enums

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

### Custom conversion (`converter` and `preprocess`)

With `@with_argparser` you can pass any callable as `add_argument(type=...)` to parse a token into a
custom value. `@with_annotated` derives `type=` from the annotation instead, and rejects a raw
`type=` in the metadata (it would silently shadow the inferred converter). Two hooks give the same
power without that footgun:

- `converter` -- a `Callable[[str], Any]` that **replaces** the inferred `type=` converter.
- `preprocess` -- a `Callable[[str], str]` that runs **before** the inferred converter.

They differ in what survives. A `converter` owns the whole conversion, so the inferred `choices` and
completer (which described the inferred value-space) are dropped. A `preprocess` only transforms the
raw token, so the inferred `type=`, `choices`, completer, and coercion are all kept.

#### `converter`: replace the conversion

Use `converter` when the annotation's built-in conversion is wrong for your input, or when the type
has no built-in conversion at all. Because the converter owns the conversion, the annotation no
longer has to be one of the supported scalar types -- any type is legal, and the usual "unsupported
type" error is suppressed:

```py
import datetime
from typing import Annotated
from cmd2.annotated import Argument, Option, with_annotated

def parse_size(value: str) -> int:
    """Parse an integer with an optional K/M/G suffix."""
    multiplier = {"K": 1_000, "M": 1_000_000, "G": 1_000_000_000}.get(value[-1:].upper(), 1)
    return int(value[:-1] if multiplier != 1 else value) * multiplier

class MyApp(cmd2.Cmd):
    @with_annotated
    def do_alloc(self, size: Annotated[int, Argument(converter=parse_size)]) -> None:
        self.poutput(f"Allocating {size} bytes")  # `alloc 64K` -> 64000

    @with_annotated
    def do_at(self, when: Annotated[datetime.datetime, Option("--when", converter=datetime.datetime.fromisoformat)]):
        self.poutput(when.isoformat())  # `datetime` has no inferred converter, so converter= makes it legal
```

argparse applies `type=` per token, so on a `list[T]` the converter runs on each value. To take a
**single** token and have the converter return a whole collection (the one-token-to-many idiom),
annotate with a non-collection type such as `Any` -- a collection annotation like `set[int]` would
instead infer `nargs` and split the input across several tokens:

```py
from typing import Annotated, Any

def parse_intset(value: str) -> set[int]:
    return {int(piece) for piece in value.split(",")}

@with_annotated
def do_select(self, idx: Annotated[Any, Option("--idx", converter=parse_intset)]) -> None:
    self.poutput(sorted(idx))  # `select --idx 1,3,5` -> [1, 3, 5]
```

An explicit `choices=` is still reconciled against the converter (its values are run through the
converter), so you can re-add a restricted choice set after replacing the conversion.

#### `preprocess`: normalize before the inferred conversion

Use `preprocess` when the inferred conversion is correct but the raw token needs massaging first.
The inferred `type=`, `choices`, and completer are kept, so an `Enum` keeps its choices and
completion while accepting normalized input, and a `Path` keeps its completer:

```py
import os
from typing import Annotated
from cmd2.annotated import Argument, with_annotated

class MyApp(cmd2.Cmd):
    @with_annotated
    def do_tag(self, color: Annotated[Color, Argument(preprocess=str.lower)]) -> None:
        self.poutput(color.value)  # `tag RED` works, and `tag <TAB>` still lists the colors

    @with_annotated
    def do_open(self, path: Annotated[Path, Argument(preprocess=os.path.expanduser)]) -> None:
        self.poutput(path)  # `open ~/file` expands, path completion still works
```

With a plain `str` (no inferred converter) the `preprocess` callable simply becomes the `type=`.

`converter` and `preprocess` are **mutually exclusive** on one parameter -- a converter already
receives the raw token, so fold the preprocessing into it. Neither may be combined with a value-less
action (`store_true`, `store_false`, `count`, `store_const`, `append_const`), which consumes no
token to convert. Both raise `TypeError` at decoration time.

## Decorator options

`@with_annotated` currently supports:

- `ns_provider` -- prepopulate the namespace before parsing, mirroring `@with_argparser`
- `preserve_quotes` -- if `True`, quotes in arguments are preserved
- `with_unknown_args` -- if `True`, unrecognised arguments are passed as `_unknown`
- `subcommand_to` -- register the function as an annotated subcommand under a parent command
- `base_command` -- create a base command whose parser also adds subparsers and exposes
  `cmd2_subcommand_func`. A `cmd2_subcommand_func` parameter is only valid on a command decorated
  with `base_command=True`; declaring one elsewhere raises `TypeError`.
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
- `**parser_kwargs` -- every other `Cmd2ArgumentParser` constructor kwarg, forwarded through PEP 692
  [`Unpack[Cmd2ParserKwargs]`][cmd2.annotated.Cmd2ParserKwargs]. See
  [Parser customization](#parser-customization) below for the full list and the `description` /
  `prog` special cases.

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

The forwarded kwargs are `description`, `epilog`, `prog`, `usage`, `parents`, `argument_default`,
`prefix_chars`, `fromfile_prefix_chars`, `conflict_handler`, `add_help`, `allow_abbrev`,
`exit_on_error`, `formatter_class`, `completer_class`, and on Python ≥ 3.14 `suggest_on_error` /
`color`. Two of them layer extra behavior on top of the raw passthrough:

- `description` -- when omitted, it is filled from the function's docstring (detailed below); pass
  an explicit value to override.
- `prog` -- rejected when `subcommand_to` is set; cmd2's subcommand machinery rewrites `prog` from
  the parent command hierarchy, so any value here would be silently overwritten.

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

`mutually_exclusive_groups` also takes `Group` instances. Pass `Group(..., required=True)` to make
the mutex group itself required -- argparse will then enforce that exactly one of its members must
be supplied. `required=True` is rejected on a plain (non-mutex) `Group` because `add_argument_group`
has no `required` flag.

```py
@with_annotated(
    mutually_exclusive_groups=(Group("verbose", "quiet", required=True),),
)
def do_run(self, verbose: bool = False, quiet: bool = False): ...
```

Give a `mutually_exclusive_groups` `Group` a `title`/`description` to render it as a titled help
section -- argparse's one supported nesting, a mutex _inside_ an argument group. You declare it
once, with no paired `groups=` entry. Use `Option(action="store_true")` on each `bool` member so the
choice reads as `[--json | --csv]` instead of expanding to `--json`/`--no-json` and
`--csv`/`--no-csv`:

```py
@with_annotated(
    mutually_exclusive_groups=(
        Group("json", "csv", title="output", description="how to write results"),
    ),
)
def do_render(
    self,
    json: Annotated[bool, Option(action="store_true")] = False,
    csv: Annotated[bool, Option(action="store_true")] = False,
): ...
```

To put non-mutex parameters in the same section, declare a `groups=` entry with all of them and
leave the title off the mutex; argparse nests the mutex inside that group. Declaring the section in
both places, a mutex that sits only partly in a `groups=` entry, or one that spans two of them, each
raises `ValueError`. The other three nestings (an argument group inside another group or a mutex, or
a mutex inside a mutex) are removed in argparse on Python 3.14 and cannot be expressed here.

All of these group-spec rules -- member references, a parameter assigned to two groups,
`required=True` on a plain group, and the mutex nesting rules above -- are validated when the
decorator runs, so a misconfigured group raises `ValueError` at class definition time instead of on
first command use. The checks read only parameter names, never the type hints, so forward-referenced
annotations still decorate cleanly. The one group rule that depends on the annotations (a member of
a mutually exclusive group must be omittable -- have a default or be `T | None`) fires when the
parser is built.

`parents=` mirrors argparse's standard parents mechanism for sharing argument definitions across
parsers. `argument_default=argparse.SUPPRESS` is not supported and raises `TypeError`. It removes an
absent argument from the parsed namespace, but `@with_annotated` builds the call from the function
signature, so every declared parameter is expected at invocation; an argument vanishing from the
namespace can never be valid here (mirroring the per-argument `default=argparse.SUPPRESS`
rejection). Any other `argument_default` value is forwarded to the parser unchanged.

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
def do_manage(self, *, cmd2_subcommand_func):
    if cmd2_subcommand_func:
        cmd2_subcommand_func()

@with_annotated(subcommand_to="manage", help="list projects")
def manage_list(self):
    self.poutput("listing")
```

For nested subcommands, `subcommand_to` can be space-delimited, for example
`subcommand_to="manage project"`. The intermediate level must also be declared as a subcommand that
creates its own subparsers:

```py
@with_annotated(subcommand_to="manage", base_command=True, help="manage projects")
def manage_project(self, *, cmd2_subcommand_func):
    if cmd2_subcommand_func:
        cmd2_subcommand_func()

@with_annotated(subcommand_to="manage project", help="add a project")
def manage_project_add(self, name: str):
    self.poutput(f"added {name}")
```

## Argument blocks

When several commands share the same group of arguments, a reusable _argument block_ removes the
duplication. Subclass the `cmd2.ArgumentBlock` trait on a `@dataclass` and annotate a parameter with
it. Each field becomes a flat command-line argument (field name == argument name), and the parsed
values are reconstructed into an instance of the dataclass that is passed to the command:

```py
from dataclasses import dataclass
from typing import Annotated
from pathlib import Path

import cmd2
from cmd2 import with_annotated
from cmd2.annotated import Option


@dataclass
class CommonArgs(cmd2.ArgumentBlock):
    verbose: Annotated[bool, Option("-v", "--verbose")] = False
    output: Annotated[Path | None, Option("--output")] = None


class App(cmd2.Cmd):
    @with_annotated
    def do_build(self, target: str, common: CommonArgs):
        self.poutput(f"{target} verbose={common.verbose} output={common.output}")
```

`build app --verbose --output /tmp/x` reconstructs `CommonArgs(verbose=True, output=Path("/tmp/x"))`
and passes it as `common`. The block parameter itself is never an argument, only its fields are.

A field carries the usual `Annotated[T, Option(...)]` / `Annotated[T, Argument(...)]` metadata and
behaves exactly as a top-level parameter of the same shape would. The dataclass is the single source
of truth for defaults: a field with a default (`default` or `default_factory`) is filled by the
dataclass constructor at call time, so `default_factory` yields a fresh value per invocation and
`__post_init__` runs. A field with no default becomes a required argument.

Inheritance is the reuse mechanism: a subclass of a block is itself a block, so a shared base block
can be extended per command without repeating its fields.

```py
@dataclass
class TracedArgs(CommonArgs):
    trace: bool = False  # do_test gets verbose, output, and trace
```

A few rules keep blocks unambiguous:

- The `ArgumentBlock` trait, not "is a dataclass", is the trigger. A plain `@dataclass` is left
  alone and can still be used as an ordinary single value (for example via
  `Argument(converter=...)`).
- A block must be the _bare_ annotation of a regular parameter. Wrapping it in
  `Annotated`/`Optional`/a union, or using it as `*args`/`**kwargs`, raises a clear error.
- Because fields expand flat, a field name that collides with another parameter or another block's
  field raises an error when the parser is built, rather than silently sharing a destination.
- A field whose type is itself a block is not expanded (no recursion); it is rejected as an
  unsupported type.

### Sharing a block with subcommands (`cmd2_base_args` / `cmd2_parent_args`)

A base command and its subcommands parse into one shared namespace. To share a block down the chain,
name the parameter `cmd2_base_args` on the command that owns the flags and `cmd2_parent_args` on
each subcommand that should receive it, annotating both with the same block type:

```py
@dataclass
class SharedOpts(cmd2.ArgumentBlock):
    verbose: Annotated[bool, Option("-v", "--verbose")] = False
    level: Annotated[int, Option("--level")] = 1


class App(cmd2.Cmd):
    @with_annotated(base_command=True)
    def do_root(self, cmd2_subcommand_func, cmd2_base_args: SharedOpts):
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    @with_annotated(subcommand_to="root", help="show the inherited block")
    def root_show(self, cmd2_parent_args: SharedOpts):
        self.poutput(f"verbose={cmd2_parent_args.verbose} level={cmd2_parent_args.level}")
```

`root --verbose --level 5 show` prints `verbose=True level=5`: the options parsed on `root` flow
into the subcommand in a typed way without being redeclared. `cmd2_base_args` adds the block's flags
to its own command's parser, while `cmd2_parent_args` adds _no_ arguments and is reconstructed from
the values an ancestor parsed (`root --verbose show`, not `root show --verbose`). A
`cmd2_parent_args` subcommand whose ancestors never declare a matching `cmd2_base_args` raises a
clear error the first time it runs. This is the typed alternative to forwarding parent-level state
through `ns_provider`.

A subcommand can also declare its own regular block alongside the inherited one. The two are
independent: the inherited block's flags are supplied on the parent, while the subcommand's own
block adds its flags to the subcommand's parser.

```py
@dataclass
class RunOpts(cmd2.ArgumentBlock):
    retries: Annotated[int, Option("--retries")] = 0


class App(cmd2.Cmd):
    @with_annotated(base_command=True)
    def do_root(self, cmd2_subcommand_func, cmd2_base_args: SharedOpts):
        if cmd2_subcommand_func:
            cmd2_subcommand_func()

    @with_annotated(subcommand_to="root")
    def root_run(self, name: str, cmd2_parent_args: SharedOpts, run: RunOpts):
        # --verbose/--level come from `root`; --retries is this subcommand's own flag
        self.poutput(f"run {name} verbose={cmd2_parent_args.verbose} retries={run.retries}")
```

`root --verbose run job --retries 3` parses `--verbose` on `root` and `--retries` on `run`.

## Lower-level parser building

[cmd2.annotated.build_parser_from_function][cmd2.annotated.build_parser_from_function] builds the
parser directly from a function without registering a command. It accepts the same `groups`,
`mutually_exclusive_groups`, `parser_class`, and forwarded
[`Unpack[Cmd2ParserKwargs]`][cmd2.annotated.Cmd2ParserKwargs] as `@with_annotated`. Like the
decorator, it skips the first parameter as the method receiver (`self`/`cls`).

```py
from cmd2.annotated import build_parser_from_function

def greet(self, name: str, count: int = 1):
    """Greet someone."""

parser = build_parser_from_function(greet)
namespace = parser.parse_args(["Alice", "--count", "3"])
# namespace.name == "Alice", namespace.count == 3
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
