API Reference
=============

These pages document the public API for ``cmd2``. If a method, class, function,
attribute, or constant is not documented here, consider it private and subject
to change. There are many classes, methods, functions, and constants in the
source code which do not begin with an underscore but are not documented here.
When looking at the source code for this library, you can not safely assume
that because something doesn't start with an underscore, it is a public API.

If a release of this library changes any of the items documented here, the
version number will be incremented according to the `Semantic Version
Specification <https://semver.org>`_.

This documentation is for ``cmd2`` version |version|.

.. toctree::
   :maxdepth: 1
   :hidden:

   cmd
   decorators
   parsing
   argparse_completer
   argparse_custom
   ansi
   utils
   history
   plugin
   py_bridge
   constants

**Modules**

- :ref:`api/cmd:cmd2.Cmd` - functions and attributes of the main
  class in this library
- :ref:`api/decorators:cmd2.decorators` - decorators for ``cmd2``
  commands
- :ref:`api/parsing:cmd2.parsing` - classes for parsing and storing
  user input
- :ref:`api/argparse_completer:cmd2.argparse_completer` - classes for
  ``argparse``-based tab completion
- :ref:`api/argparse_custom:cmd2.argparse_custom` - classes and functions
  for extending ``argparse``
- :ref:`api/ansi:cmd2.ansi` - convenience classes and functions for generating
  ANSI escape sequences to style text in the terminal
- :ref:`api/utils:cmd2.utils` - various utility classes and functions
- :ref:`api/history:cmd2.history` - classes for storing the history
  of previously entered commands
- :ref:`api/plugin:cmd2.plugin` - data classes for hook methods
- :ref:`api/py_bridge:cmd2.py_bridge` - classes for bridging calls from the
  embedded python environment to the host app
- :ref:`api/constants:cmd2.constants` - just like it says on the tin
