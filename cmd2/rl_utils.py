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

    ############################################################################################################
    # pyreadline is incomplete in terms of the Python readline API. Add the missing functions we need.
    ############################################################################################################
    # readline.redisplay()
    try:
        getattr(readline, 'redisplay')
    except AttributeError:
        # noinspection PyProtectedMember
        readline.redisplay = readline.rl.mode._update_line

    # readline.remove_history_item()
    try:
        getattr(readline, 'remove_history_item')
    except AttributeError:
        # noinspection PyProtectedMember
        def pyreadline_remove_history_item(pos: int) -> None:
            """
            An implementation of remove_history_item() for pyreadline
            :param pos: The 0-based position in history to remove
            """
            # Save of the current location of the history cursor
            saved_cursor = readline.rl.mode._history.history_cursor

            # Delete the history item
            del(readline.rl.mode._history.history[pos])

            # Update the cursor if needed
            if saved_cursor > pos:
                readline.rl.mode._history.history_cursor -= 1

        readline.remove_history_item = pyreadline_remove_history_item

elif 'gnureadline' in sys.modules or 'readline' in sys.modules:
    # We don't support libedit
    if 'libedit' not in readline.__doc__:
        rl_type = RlType.GNU

        # Load the readline lib so we can access members of it
        import ctypes
        readline_lib = ctypes.CDLL(readline.__file__)


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
