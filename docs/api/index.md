---
render_macros: true
---

# API Reference

These pages document the public API for `cmd2`. If a method, class, function, attribute, or constant is not documented here, consider it private and subject to change. There are many classes, methods, functions, and constants in the source code which do not begin with an underscore but are not documented here. When looking at the source code for this library, you cannot safely assume that because something doesn't start with an underscore, it is a public API.

If a release of this library changes any of the items documented here, the version number will be incremented according to the [Semantic Version Specification](https://semver.org).

This documentation is for `cmd2` version {{ version }}.

**Modules**

-   `api/cmd:cmd2.Cmd`{.interpreted-text role="ref"} - functions and attributes of the main class in this library
-   `api/ansi:cmd2.ansi`{.interpreted-text role="ref"} - convenience classes and functions for generating ANSI escape sequences to style text in the terminal
-   `api/argparse_completer:cmd2.argparse_completer`{.interpreted-text role="ref"} - classes for `argparse`-based tab completion
-   `api/argparse_custom:cmd2.argparse_custom`{.interpreted-text role="ref"} - classes and functions for extending `argparse`
-   `api/command_definition:cmd2.command_definition`{.interpreted-text role="ref"} - supports the definition of commands in separate classes to be composed into cmd2.Cmd
-   `api/constants:cmd2.constants`{.interpreted-text role="ref"} - just like it says on the tin
-   `api/decorators:cmd2.decorators`{.interpreted-text role="ref"} - decorators for `cmd2` commands
-   `api/exceptions:cmd2.exceptions`{.interpreted-text role="ref"} - custom `cmd2` exceptions
-   `api/history:cmd2.history`{.interpreted-text role="ref"} - classes for storing the history of previously entered commands
-   `api/parsing:cmd2.parsing`{.interpreted-text role="ref"} - classes for parsing and storing user input
-   `api/plugin:cmd2.plugin`{.interpreted-text role="ref"} - data classes for hook methods
-   `api/py_bridge:cmd2.py_bridge`{.interpreted-text role="ref"} - classes for bridging calls from the embedded python environment to the host app
-   `api/table_creator:cmd2.table_creator`{.interpreted-text role="ref"} - table creation module
-   `api/utils:cmd2.utils`{.interpreted-text role="ref"} - various utility classes and functions
-   `api/plugin_external_test:cmd2_ext_test`{.interpreted-text role="ref"} - External test plugin
