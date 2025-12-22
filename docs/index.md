# cmd2

A :simple-python: Python package for building powerful command-line interpreter (CLI) programs.
Extends the Python Standard Library's [cmd](https://docs.python.org/3/library/cmd.html) package.

The basic use of `cmd2` is identical to that of [cmd](https://docs.python.org/3/library/cmd.html).

1.  Create a subclass of [cmd2.Cmd][]. Define attributes and `do_*` methods to control its behavior.
    Throughout this documentation, we will assume that you are naming your subclass `App`:

```py title="Creating a class inherited from cmd2.Cmd" linenums="1"
from cmd2 import Cmd
class App(Cmd):
   # customized attributes and methods here
```

2.  Instantiate `App` and start the command loop:

```py title="Instantiating and starting a cmd2 app" linenums="1" hl_lines="5-6"
from cmd2 import Cmd
class App(Cmd):
   # customized attributes and methods here

app = App()
app.cmdloop()
```

## Getting Started

See the [Getting Started](overview/index.md) section for info on how to get started building a
`cmd2` application.

## Migrating from cmd2

See the [Migrating from cmd2](migrating/index.md) section for info on how to migrate a `cmd`
application to `cmd2`.

## Features

See the [Features](features/index.md) section for a detailed guide to the features available within
`cmd2`.

## Examples

See the [Examples](examples/index.md) section for various examples of using `cmd2`.

## Mixins

See the [Mixins](mixins/index.md) section for info on how to extend `cmd2` using mixins.

## Testing

See the [Testing](testing.md) section for special considerations when writing unit or integration
tests for a `cmd2` application.

## API Reference

See the [API Reference](api/index.md) for detailed information on the public API of `cmd2`.

## Meta

See the [Documentation Conventions](doc_conventions.md) for info on conventions used in this
documentation.
