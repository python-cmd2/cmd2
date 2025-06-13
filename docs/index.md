# cmd2

A python package for building powerful command-line interpreter (CLI) programs. Extends the Python
Standard Library's [cmd](https://docs.python.org/3/library/cmd.html) package.

The basic use of `cmd2` is identical to that of [cmd](https://docs.python.org/3/library/cmd.html).

1.  Create a subclass of [cmd2.Cmd][]. Define attributes and `do_*` methods to control its behavior.
    Throughout this documentation, we will assume that you are naming your subclass `App`:

```py title="Creating a class inherited from cmd2.Cmd" linenums="1"
from cmd2 import Cmd
class App(Cmd):
   # customized attributes and methods here
```

2.  Instantiate `App` and start the command loop:

```py title="Instatiating and starting a cmd2 app" linenums="1" hl_lines="5-6"
from cmd2 import Cmd
class App(Cmd):
   # customized attributes and methods here

app = App()
app.cmdloop()
```

## Getting Started

{%
   include-markdown "./overview/index.md"
%}

## Migrating from cmd

{%
   include-markdown "./migrating/index.md"
%}

## Features

{%
   include-markdown "./features/index.md"
    start="<!--intro-start-->"
    end="<!--intro-end-->"
%}

## Examples

{%
   include-markdown "./examples/index.md"
    start="<!--intro-start-->"
    end="<!--intro-end-->"
%}

## Plugins

{%
   include-markdown "./plugins/index.md"
    start="<!--intro-start-->"
    end="<!--intro-end-->"
%}

## [Testing](testing.md)

## [API Reference](api/index.md)

## Meta

[Documentation Conventions](doc_conventions.md)
