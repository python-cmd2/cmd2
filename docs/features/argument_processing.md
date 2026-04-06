# Argument Processing

`cmd2` makes it easy to add sophisticated argument processing to your commands using the
[argparse](https://docs.python.org/3/library/argparse.html) python module. `cmd2` handles the
following for you:

1. Parsing input and quoted strings in a manner similar to how POSIX shells do it
1. Parse the resulting argument list using an instance of
   [Cmd2ArgumentParser](https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser)
   that you provide
1. Passes the resulting
   [argparse.Namespace](https://docs.python.org/3/library/argparse.html#argparse.Namespace) object
   to your command function. The `Namespace` includes the [Statement][cmd2.Statement] object that
   was created when parsing the command line. It is accessible via the `cmd2_statement` attribute on
   the `Namespace`.
1. Adds the usage message from the argument parser to your command's help.
1. Checks if the `-h/--help` option is present, and if so, displays the help message for the command

These features are provided by two decorators:

- [@with_argparser][cmd2.with_argparser] -- build parsers manually with `add_argument()` calls
- [@with_annotated][cmd2.decorators.with_annotated] -- build parsers automatically from type hints

See the
[argparse_completion](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_completion.py)
and [annotated_example](https://github.com/python-cmd2/cmd2/blob/main/examples/annotated_example.py)
examples to compare the two styles side by side.

`cmd2` provides the following [decorators](../api/decorators.md) for assisting with parsing
arguments passed to commands:

- [cmd2.decorators.with_argparser][]
- [cmd2.decorators.with_annotated][]
- [cmd2.decorators.with_argument_list][]

All of these decorators accept an optional **preserve_quotes** argument which defaults to `False`.
Setting this argument to `True` is useful for cases where you are passing the arguments to another
command which might have its own argument parsing.

## with_argparser decorator

The [@with_argparser][cmd2.with_argparser] decorator can accept the following for its first
argument:

1. An existing instance of `Cmd2ArgumentParser`
2. A function or static method which returns an instance of `Cmd2ArgumentParser`
3. Cmd or CommandSet class method which returns an instance of `Cmd2ArgumentParser`

In all cases the `@with_argparser` decorator creates a deep copy of the parser instance which it
stores internally. A consequence is that parsers don't need to be unique across commands.

!!! warning

    Since the `@with_argparser` decorator is making a deep-copy of the parser provided, if you wish
    to dynamically modify this parser at a later time, you need to retrieve this deep copy. This can
    be done using `self._command_parsers.get(self.do_commandname)`.

## with_annotated decorator

The [@with_annotated][cmd2.decorators.with_annotated] decorator builds an argparse parser
automatically from the decorated function's type annotations. No manual `add_argument()` calls are
required.

### Basic usage

Parameters without defaults become positional arguments. Parameters with defaults become `--option`
flags. Keyword-only parameters (after `*`) always become options, and without a default they become
required options. The function receives typed keyword arguments directly instead of an
`argparse.Namespace`.

```py
from cmd2 import with_annotated

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

### How annotations map to argparse

The decorator converts Python type annotations into `add_argument()` calls:

| Type annotation                                          | Generated argparse setting                          |
| -------------------------------------------------------- | --------------------------------------------------- |
| `str`                                                    | default (no `type=` needed)                         |
| `int`, `float`                                           | `type=int` or `type=float`                          |
| `bool` with a default                                    | boolean optional flag via `BooleanOptionalAction`   |
| positional `bool`                                        | parsed from `true/false`, `yes/no`, `on/off`, `1/0` |
| `Path`                                                   | `type=Path`                                         |
| `Enum` subclass                                          | `type=converter`, `choices` from member values      |
| `decimal.Decimal`                                        | `type=decimal.Decimal`                              |
| `Literal[...]`                                           | `type=literal-converter`, `choices` from values     |
| `Collection[T]` / `list[T]` / `set[T]` / `tuple[T, ...]` | `nargs='+'` (or `'*'` if it has a default)          |
| `tuple[T, T]`                                            | fixed `nargs=N` with `type=T`                       |
| `T \| None`                                              | unwrapped to `T`, treated as optional               |

When collection types are used with `@with_annotated`, parsed values are passed to the command
function as:

- `list[T]` and `Collection[T]` as `list`
- `set[T]` as `set`
- `tuple[T, ...]` as `tuple`

Unsupported patterns raise `TypeError`, including:

- unions with multiple non-`None` members such as `str | int`
- mixed-type tuples such as `tuple[int, str]`
- `Annotated[T, meta] | None`; write `Annotated[T | None, meta]` instead

The parameter names `dest` and `subcommand` are reserved and may not be used as annotated parameter
names.

### Annotated metadata

For finer control, use `typing.Annotated` with [Argument][cmd2.annotated.Argument] or
[Option][cmd2.annotated.Option] metadata:

```py
from typing import Annotated
from cmd2 import Argument, Option, with_annotated

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

### Comparison with @with_argparser

The two decorators are interchangeable. Here is the same command written both ways:

**@with_argparser**

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

**@with_annotated**

```py
@with_annotated
def do_greet(self, name: str, count: int = 1, loud: bool = False):
    for _ in range(count):
        msg = f"Hello {name}"
        self.poutput(msg.upper() if loud else msg)
```

The annotated version is more concise and gives you typed parameters. It also supports several
advanced cmd2 features directly, including `ns_provider`, `with_unknown_args`, and typed
subcommands.

### Decorator options

`@with_annotated` currently supports:

- `ns_provider` -- prepopulate the namespace before parsing, mirroring `@with_argparser`
- `preserve_quotes` -- if `True`, quotes in arguments are preserved
- `with_unknown_args` -- if `True`, unrecognised arguments are passed as `_unknown`
- `subcommand_to` -- register the function as an annotated subcommand under a parent command
- `base_command` -- create a base command whose parser also adds subparsers and exposes
  `cmd2_handler`
- `help` -- help text for an annotated subcommand
- `aliases` -- aliases for an annotated subcommand

```py
@with_annotated(with_unknown_args=True)
def do_rawish(self, name: str, _unknown: list[str] | None = None):
    self.poutput((name, _unknown))
```

### Annotated subcommands

`@with_annotated` can also build typed subcommand trees without manually constructing subparsers.

```py
@with_annotated(base_command=True)
def do_manage(self, *, cmd2_handler):
    handler = cmd2_handler.get()
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
    handler = cmd2_handler.get()
    if handler:
        handler()

@with_annotated(subcommand_to="manage project", help="add a project")
def manage_project_add(self, name: str):
    self.poutput(f"added {name}")
```

### Lower-level parser building

If you need parser grouping or mutually-exclusive groups while still using annotation-driven parser
generation, [cmd2.annotated.build_parser_from_function][cmd2.annotated.build_parser_from_function]
also supports:

- `groups=((...), (...))`
- `mutually_exclusive_groups=((...), (...))`

```py
@with_annotated(preserve_quotes=True)
def do_raw(self, text: str):
    self.poutput(f"raw: {text}")
```

## Automatic Completion from Types

With `@with_annotated`, arguments annotated as `Path` or `Enum` get automatic completion without
needing an explicit `choices_provider` or `completer`.

Specifically:

- `Path` (or any `Path` subclass) triggers filesystem path completion
- `MyEnum` (any `enum.Enum` subclass) triggers completion from enum member values

With `@with_argparser`, provide `choices`, `choices_provider`, or `completer` explicitly when you
want completion behavior.

## Argument Parsing

For each command in the `cmd2.Cmd` subclass which requires argument parsing, create an instance of
`Cmd2ArgumentParser` which can parse the input appropriately for the command (or provide a
function/method that returns such a parser). Then decorate the command method with the
`@with_argparser` decorator, passing the argument parser as the first parameter to the decorator.
This changes the second argument of the command method, which will contain the results of
`Cmd2ArgumentParser.parse_args()`.

Here's what it looks like:

```py
from cmd2 import Cmd2ArgumentParser, with_argparser

argparser = Cmd2ArgumentParser()
argparser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
argparser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
argparser.add_argument('-r', '--repeat', type=int, help='output [n] times')
argparser.add_argument('word', nargs='?', help='word to say')

@with_argparser(argparser)
def do_speak(self, opts):
    """Repeats what you tell me to."""
    arg = opts.word
    if opts.piglatin:
        arg = '%s%say' % (arg[1:], arg[0])
    if opts.shout:
        arg = arg.upper()
    repetitions = opts.repeat or 1
    for i in range(min(repetitions, self.maxrepeats)):
        self.poutput(arg)
```

!!! note

    `cmd2` sets the `prog` variable in the argument parser based on the name of the method it is decorating.
    This will override anything you specify in `prog` variable when creating the argument parser.

    As of the 3.0.0 release, `cmd2` sets `prog` when the instance-specific parser is created, which is later
    than in previous versions.

## Help Messages

By default, `cmd2` uses the docstring of the command method when a user asks for help on the
command. When you use the `@with_argparser` decorator, the docstring for the `do_*` method is used
to set the description for the `Cmd2ArgumentParser`.

!!! tip "description and epilog fields are rich objects"

    While the `help` field is simply a string, both the `description` and `epilog` fields can accept any
    [rich](https://github.com/Textualize/rich) renderable. This allows you to include all of rich's
    built-in objects like `Text`, `Table`, and `Markdown`.

With this code:

```py
from cmd2 import Cmd2ArgumentParser, with_argparser

argparser = Cmd2ArgumentParser()
argparser.add_argument('tag', help='tag')
argparser.add_argument('content', nargs='+', help='content to surround with tag')
@with_argparser(argparser)
def do_tag(self, args):
    """Create an HTML tag"""
    self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
    self.stdout.write('\n')
```

the `help tag` command displays:

```text
usage: tag [-h] tag content [content ...]

Create an HTML tag

positional arguments:
  tag         tag
  content     content to surround with tag

optional arguments:
  -h, --help  show this help message and exit
```

If you would prefer, you can set the `description` while instantiating the `Cmd2ArgumentParser` and
leave the docstring on your method blank:

```py
from cmd2 import Cmd2ArgumentParser, with_argparser

argparser = Cmd2ArgumentParser(description='create an HTML tag')
argparser.add_argument('tag', help='tag')
argparser.add_argument('content', nargs='+', help='content to surround with tag')
@with_argparser(argparser)
def do_tag(self, args):
    self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
    self.stdout.write('\n')
```

Now when the user enters `help tag` they see:

```text
usage: tag [-h] tag content [content ...]

create an HTML tag

positional arguments:
  tag         tag
  content     content to surround with tag

optional arguments:
  -h, --help  show this help message and exit
```

To add additional text to the end of the generated help message, use the `epilog` variable:

```py
from cmd2 import Cmd2ArgumentParser, with_argparser

argparser = Cmd2ArgumentParser(description='create an HTML tag',
                                epilog='This command cannot generate tags with no content, like <br/>.')
argparser.add_argument('tag', help='tag')
argparser.add_argument('content', nargs='+', help='content to surround with tag')
@with_argparser(argparser)
def do_tag(self, args):
    self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
    self.stdout.write('\n')
```

Which yields:

```text
usage: tag [-h] tag content [content ...]

create an HTML tag

positional arguments:
  tag         tag
  content     content to surround with tag

optional arguments:
  -h, --help  show this help message and exit

This command cannot generate tags with no content, like <br/>
```

!!! warning

    If a command **foo** is decorated with `cmd2`'s `with_argparse` decorator, then **help_foo** will not be
    invoked when `help foo` is called. The [argparse](https://docs.python.org/3/library/argparse.html) module
    provides a rich API which can be used to tweak every aspect of the displayed help and we encourage `cmd2`
    developers to utilize that.

### Argparse HelpFormatter classes

`cmd2` has 5 different Argparse HelpFormatter classes, all of which are based on the
`RichHelpFormatter` class from [rich-argparse](https://github.com/hamdanal/rich-argparse). The
benefit is that your `cmd2` applications now have more aesthetically pleasing help which includes
color to make it quicker and easier to visually parse help text. This works for all supported
versions of Python.

- [Cmd2HelpFormatter][cmd2.argparse_custom.Cmd2HelpFormatter] - default help formatter class
- [ArgumentDefaultsCmd2HelpFormatter][cmd2.argparse_custom.ArgumentDefaultsCmd2HelpFormatter] - adds
  default values to argument help
- [MetavarTypeCmd2HelpFormatter][cmd2.argparse_custom.MetavarTypeCmd2HelpFormatter] - uses the
  argument 'type' as the default metavar value (instead of the argument 'dest')
- [RawDescriptionCmd2HelpFormatter][cmd2.argparse_custom.RawDescriptionCmd2HelpFormatter] - retains
  any formatting in descriptions and epilogs
- [RawTextCmd2HelpFormatter][cmd2.argparse_custom.RawTextCmd2HelpFormatter] - retains formatting of
  all help text

The default `Cmd2HelpFormatter` class inherits from `argparse.HelpFormatter`. If you want a
different behavior, then pass the desired class to the `formatter_class` argument of your argparse
parser, e.g. `formatter_class=ArgumentDefaultsCmd2HelpFormatter` to your parser.

## Argument List

The default behavior of `cmd2` is to pass the user input directly to your `do_*` methods as a
string. The object passed to your method is actually a [Statement][cmd2.Statement] object, which has
additional attributes that may be helpful, including `arg_list` and `argv`:

```py
class CmdLineApp(cmd2.Cmd):
    """ Example cmd2 application. """

    def do_say(self, statement):
        # statement contains a string
        self.poutput(statement)

    def do_speak(self, statement):
        # statement also has a list of arguments
        # quoted arguments remain quoted
        for arg in statement.arg_list:
            self.poutput(arg)

    def do_articulate(self, statement):
        # statement.argv contains the command
        # and the arguments, which have had quotes
        # stripped
        for arg in statement.argv:
            self.poutput(arg)
```

If you don't want to access the additional attributes on the string passed to your `do_*` method you
can still have `cmd2` apply shell parsing rules to the user input and pass you a list of arguments
instead of a string. Apply the [@with_argument_list][cmd2.with_argument_list] decorator to those
methods that should receive an argument list instead of a string:

```py
from cmd2 import with_argument_list

class CmdLineApp(cmd2.Cmd):
    """ Example cmd2 application. """

    def do_say(self, cmdline):
        # cmdline contains a string
        pass

    @with_argument_list
    def do_speak(self, arglist):
        # arglist contains a list of arguments
        pass
```

## Unknown Positional Arguments

To pass all unknown arguments to your command as a list of strings, then decorate the command method
with the `@with_argparser(..., with_unknown_args=True)` decorator.

Here's what it looks like:

```py
from cmd2 import Cmd2ArgumentParser, with_argparser

dir_parser = Cmd2ArgumentParser()
dir_parser.add_argument('-l', '--long', action='store_true',
                        help="display in long format with one item per line")

@with_argparser(dir_parser, with_unknown_args=True)
def do_dir(self, args, unknown):
    """List contents of current directory."""
    # No arguments for this command
    if unknown:
        self.perror("dir does not take any positional arguments:")
        self.do_help('dir')
        self.last_result = 'Bad arguments'
        return

    # Get the contents as a list
    contents = os.listdir(self.cwd)

    ...
```

## Using A Custom Namespace

In some cases, it may be necessary to write custom `argparse` code that is dependent on your
application's state data. To support this ability while still allowing use of the decorators,
`@with_argparser` has an optional argument called `ns_provider`.

`ns_provider` is a Callable that accepts a `cmd2.Cmd` object as an argument and returns an
`argparse.Namespace`:

```py
Callable[[cmd2.Cmd], argparse.Namespace]
```

For example:

```py
def settings_ns_provider(self) -> argparse.Namespace:
    """Populate an argparse Namespace with current settings"""
    ns = argparse.Namespace()
    ns.app_settings = self.settings
    return ns
```

To use this function with the `@with_argparser` decorator, do the following:

```py
@with_argparser(my_parser, ns_provider=settings_ns_provider)
```

The Namespace is passed by the decorators to the `argparse` parsing functions, giving your custom
code access to the state data it needs for its parsing logic.

## Subcommands

Subcommands are supported for commands using the `@with_argparser` decorator. The syntax is based on
argparse sub-parsers.

You may add multiple layers of subcommands for your command. `cmd2` will automatically traverse and
tab complete subcommands for all commands using argparse.

See the
[argparse_example](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_example.py)
example to learn more about how to use subcommands in your `cmd2` application.

The [@as_subcommand_to][cmd2.as_subcommand_to] decorator makes adding subcommands easy.

## Argparse Extensions

`cmd2` augments the standard `argparse.nargs` with range tuple capability:

- `nargs=(5,)` - accept 5 or more items
- `nargs=(8, 12)` - accept 8 to 12 items

`cmd2` also provides the [Cmd2ArgumentParser][cmd2.Cmd2ArgumentParser] class which inherits from
`argparse.ArgumentParser` and improves error and help output.

## Decorator Order

If you are using custom decorators in combination with `@cmd2.with_argparser`, then the order of
your custom decorator(s) relative to the `cmd2` decorator affects runtime behavior and `argparse`
errors. There is nothing `cmd2`-specific here, this is just a side-effect of how decorators work in
Python. To learn more about how decorators work, see
[decorator_primer](https://realpython.com/primer-on-python-decorators).

If you want your custom decorator's runtime behavior to occur in the case of an `argparse` error,
then that decorator needs to go **after** the `argparse` one, e.g.:

```py
@cmd2.with_argparser(foo_parser)
@my_decorator
def do_foo(self, args: argparse.Namespace) -> None:
    """foo docs"""
    pass
```

However, if you do NOT want the custom decorator runtime behavior to occur during an `argparse`
error, then that decorator needs to go **before** the `argparse` one, e.g.:

```py
@my_decorator
@cmd2.with_argparser(bar_parser)
def do_bar(self, args: argparse.Namespace) -> None:
    """bar docs"""
    pass
```

The [help_categories](https://github.com/python-cmd2/cmd2/blob/main/examples/help_categories.py)
example demonstrates both above cases in a concrete fashion.

## Reserved Argument Names

`cmd2`'s `@with_argparser` decorator adds the following attributes to argparse Namespaces. To avoid
naming collisions, do not use any of these names for your argparse arguments.

- `cmd2_statement` - [cmd2.Statement][] object that was created when parsing the command line.
- `cmd2_subcmd_handler` - subcommand handler function or `None` if one was not set.
