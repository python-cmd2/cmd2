# API Reference

These pages document the public API for `cmd2`. If a method, class, function, attribute, or constant
is not documented here, consider it private and subject to change. There are many classes, methods,
functions, and constants in the source code that do not begin with an underscore but are not
documented here. When looking at the source code for this library, you cannot safely assume that
something is a public API just because it doesn't start with an underscore.

If a release of this library changes any of the items documented here, the version number will be
incremented according to the [Semantic Version Specification](https://semver.org).

## Modules

- [cmd2.Cmd](./cmd.md) - functions and attributes of the main class in this library
- [cmd2.argparse_completer](./argparse_completer.md) - classes for `argparse`-based tab completion
- [cmd2.argparse_custom](./argparse_custom.md) - classes and functions for extending `argparse`
- [cmd2.clipboard](./clipboard.md) - functions to copy from and paste to the clipboard/pastebuffer
- [cmd2.colors](./colors.md) - StrEnum of all color names supported by the Rich library
- [cmd2.command_definition](./command_definition.md) - supports the definition of commands in
  separate classes to be composed into cmd2.Cmd
- [cmd2.constants](./constants.md) - constants used in `cmd2`
- [cmd2.decorators](./decorators.md) - decorators for `cmd2` commands
- [cmd2.exceptions](./exceptions.md) - custom `cmd2` exceptions
- [cmd2.history](./history.md) - classes for storing the history of previously entered commands
- [cmd2.parsing](./parsing.md) - classes for parsing and storing user input
- [cmd2.plugin](./plugin.md) - data classes for hook methods
- [cmd2.py_bridge](./py_bridge.md) - classes for bridging calls from the embedded python environment
  to the host app
- [cmd2.rich_utils](./rich_utils.md) - common utilities to support Rich in cmd2 applications
- [cmd2.rl_utils](./rl_utils.md) - imports the proper Readline for the platform and provides utility
  functions for it
- [cmd2.string_utils](./string_utils.md) - string utility functions
- [cmd2.styles](./styles.md) - cmd2-specific Rich styles and a StrEnum of their corresponding names
- [cmd2.terminal_utils](./terminal_utils.md) - support for terminal control escape sequences
- [cmd2.transcript](./transcript.md) - functions and classes for running and validating transcripts
- [cmd2.utils](./utils.md) - various utility classes and functions
