# API Reference

These pages document the public API for `cmd2`. If a method, class, function, attribute, or constant
is not documented here, consider it private and subject to change. There are many classes, methods,
functions, and constants in the source code which do not begin with an underscore but are not
documented here. When looking at the source code for this library, you cannot safely assume that
because something doesn't start with an underscore, it is a public API.

If a release of this library changes any of the items documented here, the version number will be
incremented according to the [Semantic Version Specification](https://semver.org).

## Modules

- [cmd2.Cmd](./cmd.md) - functions and attributes of the main class in this library
- [cmd2.ansi](./ansi.md) - convenience classes and functions for generating ANSI escape sequences to
  style text in the terminal
- [cmd2.argparse_completer](./argparse_completer.md) - classes for `argparse`-based tab completion
- [cmd2.argparse_custom](./argparse_custom.md) - classes and functions for extending `argparse`
- [cmd2.command_definition](./command_definition.md) - supports the definition of commands in
  separate classes to be composed into cmd2.Cmd
- [cmd2.constants](./constants.md) - just like it says on the tin
- [cmd2.decorators](./decorators.md) - decorators for `cmd2` commands
- [cmd2.exceptions](./exceptions.md) - custom `cmd2` exceptions
- [cmd2.history](./history.md) - classes for storing the history of previously entered commands
- [cmd2.parsing](./parsing.md) - classes for parsing and storing user input
- [cmd2.plugin](./plugin.md) - data classes for hook methods
- [cmd2.py_bridge](./py_bridge.md) - classes for bridging calls from the embedded python environment
  to the host app
- [cmd2.table_creator](./table_creator.md) - table creation module
- [cmd2.utils](./utils.md) - various utility classes and functions
