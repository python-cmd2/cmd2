# cmd2 Major Versions Upgrades

## Upgrading to cmd2 3.x from 2.x

For details about all of the changes in the 3.0.0 release, please refer to
[CHANGELOG.md](https://github.com/python-cmd2/cmd2/blob/main/CHANGELOG.md).

The biggest change from 2.x to 3.x is that `cmd2` now has a dependency on
[rich](https://github.com/Textualize/rich). Accordingly, `cmd2` now relies on `rich` for beautiful
text styling and formatting within the terminal. As such, a good chunk of custom code has been
removed from `cmd2` and other things have either moved or altered to be based on `rich`.

The major things users should be aware of when upgrading to 3.x are detailed in subsections below.

### Deleted Modules

#### ansi

The functionality within the `cmd2.ansi` module has either been removed or changed to be based on
`rich` and moved to one of the new modules: [cmd2.string_utils][], [cmd2.styles][], or
[cmd2.terminal_utils][].

To ease the migration path from `cmd2` 2.x to 3.x, we have created the `cmd2-ansi` module which is a
backport of the `cmd2.ansi` module present in `cmd2` 2.7.0 in a standalone fashion. Relevant links:

- PyPI: [cmd2-ansi](https://pypi.org/project/cmd2-ansi/)
- GitHub: [cmd2-ansi](https://github.com/python-cmd2/cmd2-ansi)

To use this backport:

```Python
from cmd2_ansi import ansi
```

#### table_creator

The `cmd2.table_creator` module no longer exists. Please see rich's documentation on
[Tables](https://rich.readthedocs.io/en/latest/tables.html) for more information. The
[rich_tables.py](https://github.com/python-cmd2/cmd2/blob/main/examples/rich_tables.py) example
demonstrates how to use `rich` tables in a `cmd2` application.

`rich` tables offer a degree of power and flexibility that are superior to what `cmd2` previously
offered. We apologize for this backwards incompatibility, but the APIs were fundamentally different
and we could not figure out a way to create a backwards-compatibility wrapper.

To ease the migration path from `cmd2` 2.x to 3.x, we have created the `cmd2-table` module which is
a backport of the `cmd2.table_creator` module present in `cmd2` 2.7.0 in a standalone fashion.
Relevant links:

- PyPI: [cmd2-table](https://pypi.org/project/cmd2-table/)
- GitHub: [cmd2-table](https://github.com/python-cmd2/cmd2-table)

To use this backport:

```Python
from cmd2_table import table_creator
```

### Added modules

#### colors

The new [cmd2.colors][] module provides the convenient [cmd2.colors.Color][] `StrEnum` class for
`rich` color names. This allows you to use tab-completable constants in your code instead of magic
strings to represent the precise color you want.

See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py) for
a basic example of using the `Color` class to choose colors for stylizing your output.
Alternatively, see the [color.py](https://github.com/python-cmd2/cmd2/blob/main/examples/color.py)
example for a visual demonstration of all supported colors.

#### rich_utils

The new [cmd2.rich_utils][] module provides common utility classes and functions for supporting the
use of `rich` within `cmd2` applications. Most of what is here is not intended to be user-facing.

The one thing many `cmd2` application developers will likely be interested in using is the
[cmd2.rich_utils.set_theme][] function. See the
[rich_theme.py](https://github.com/python-cmd2/cmd2/blob/main/examples/rich_theme.py) example for a
demonstration for how to set a theme (color scheme) for your app.

#### styles

Default styles for how something like an error message should be displayed are now located in the
new [cmd2.styles][] module and they are now based on `rich` styles.

Previously `cmd2` default styles were in the `cmd2.ansi` module.

See
[argparse_completion.py](https://github.com/python-cmd2/cmd2/blob/main/examples/argparse_completion.py)
for an example on how you can leverage these default styles in your `cmd2` application to maintain a
consistent look and feel.

#### string_utils

Various string utility functions have been moved from the `cmd2.ansi` module to the new
[cmd2.string_utils][] module.

This includes functions for styling, aligning, and quoting/un-quoting text. See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example for a demonstration of how to use the common [cmd2.string_utils.stylize][] function.

#### terminal_utils

Support for terminal control escape sequences for things like setting the window title and
asynchronous alerts has been moved from `cmd2.ansi` to the new [cmd2.terminal_utils][] module.

This isn't really intended to be used by end users, but is used by higher-level functionality that
is intended to be used by end users such as [cmd2.Cmd.set_window_title][] and
[cmd2.Cmd.async_alert][].

See [async_printing.py](https://github.com/python-cmd2/cmd2/blob/main/examples/async_printing.py)
for an example of how to use this functionality in a `cmd2` application.

### Argparse HelpFormatter classes

`cmd2` now has 5 different Argparse HelpFormatter classes, all of which are based on the
`RichHelpFormatter` class from [rich-argparse](https://github.com/hamdanal/rich-argparse).

- [Cmd2HelpFormatter][cmd2.argparse_custom.Cmd2HelpFormatter]
- [ArgumentDefaultsCmd2HelpFormatter][cmd2.argparse_custom.ArgumentDefaultsCmd2HelpFormatter]
- [MetavarTypeCmd2HelpFormatter][cmd2.argparse_custom.MetavarTypeCmd2HelpFormatter]
- [RawDescriptionCmd2HelpFormatter][cmd2.argparse_custom.RawDescriptionCmd2HelpFormatter]
- [RawTextCmd2HelpFormatter][cmd2.argparse_custom.RawTextCmd2HelpFormatter]

Previously the default `Cmd2HelpFormatter` class inherited from `argparse.RawTextHelpFormatter`,
however it now inherits from `argparse.HelpFormatter`. If you want RawText behavior, then pass
`formatter_class=RawTextCmd2HelpFormatter` to your parser.

The benefit is that your `cmd2` applications now have more aesthetically pleasing help which
includes color to make it quicker and easier to visually parse help text. This works for all
supported versions of Python.

### Other Changes

- The `auto_load_commands` argument to `cmd2.Cmd.__init__` now defaults to `False`
- Replaced `Settable.get_value()` and `Settable.set_value()` methods with a more Pythonic `value`
  property
- Removed redundant setting of a parser's `prog` value in the `with_argparser()` decorator, as this
  is now handled centrally in `Cmd._build_parser()`
