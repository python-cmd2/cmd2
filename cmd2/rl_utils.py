# coding=utf-8
"""
Imports the proper readline for the platform and provides utility functions for it
"""
from enum import Enum
import sys

# Prefer statically linked gnureadline if available (for macOS compatibility due to issues with libedit)
try:
    import gnureadline as readline
except ImportError:
    # Try to import readline, but allow failure for convenience in Windows unit testing
    # Note: If this actually fails, you should install readline on Linux or Mac or pyreadline on Windows
    try:
        # noinspection PyUnresolvedReferences
        import readline
    except ImportError:  # pragma: no cover
        pass


class RlType(Enum):
    """Readline library types we recognize"""
    GNU = 1
    PYREADLINE = 2
    NONE = 3


# Check what implementation of readline we are using
rl_type = RlType.NONE

# The order of this check matters since importing pyreadline will also show readline in the modules list
if 'pyreadline' in sys.modules:
    rl_type = RlType.PYREADLINE

elif 'gnureadline' in sys.modules or 'readline' in sys.modules:
    # We don't support libedit
    if 'libedit' not in readline.__doc__:
        rl_type = RlType.GNU

        # Load the readline lib so we can access members of it
        import ctypes
        readline_lib = ctypes.CDLL(readline.__file__)

if rl_type != RlType.NONE:

    # Save off original values for some readline parameters to use with the rlcompleter module
    # when cmd2 enters an interactive Python shell via the py command. Saving these values off
    # here assumes no changes have been made to readline yet.

    # Save the original delimiters from Python's readline module. These are used by the rlcompleter
    # module for completing valid Python identifiers and keywords.
    rlcompleter_delims = readline.get_completer_delims()

    if rl_type == RlType.GNU:
        # Save the original basic quote characters of readline to use with rlcompleter module.
        rl_basic_quote_characters = ctypes.c_char_p.in_dll(readline_lib, "rl_basic_quote_characters")
        rlcompleter_basic_quotes = ctypes.cast(rl_basic_quote_characters, ctypes.c_void_p).value

def rl_force_redisplay() -> None:
    """
    Causes readline to redraw prompt and input line
    """
    if not sys.stdout.isatty():
        return

    if rl_type == RlType.GNU:  # pragma: no cover
        # rl_forced_update_display() is the proper way to redraw the prompt and line, but we
        # have to use ctypes to do it since Python's readline API does not wrap the function
        readline_lib.rl_forced_update_display()

        # After manually updating the display, readline asks that rl_display_fixed be set to 1 for efficiency
        display_fixed = ctypes.c_int.in_dll(readline_lib, "rl_display_fixed")
        display_fixed.value = 1

    elif rl_type == RlType.PYREADLINE:  # pragma: no cover
        # noinspection PyProtectedMember
        readline.rl.mode._print_prompt()
