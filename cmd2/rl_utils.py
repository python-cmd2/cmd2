# coding=utf-8
"""
Imports the proper readline for the platform and provides utility functions for it
"""
import sys
from enum import Enum

# Prefer statically linked gnureadline if available (for macOS compatibility due to issues with libedit)
try:
    # noinspection PyPackageRequirements
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

# Tells if the terminal we are running in supports vt100 control characters
vt100_support = False

# Explanation for why readline wasn't loaded
_rl_warn_reason = ''

# The order of this check matters since importing pyreadline will also show readline in the modules list
if 'pyreadline' in sys.modules:
    rl_type = RlType.PYREADLINE

    from ctypes import byref
    from ctypes.wintypes import DWORD, HANDLE
    import atexit

    # Check if we are running in a terminal
    if sys.stdout.isatty():  # pragma: no cover
        # noinspection PyPep8Naming,PyUnresolvedReferences
        def enable_win_vt100(handle: HANDLE) -> bool:
            """
            Enables VT100 character sequences in a Windows console
            This only works on Windows 10 and up
            :param handle: the handle on which to enable vt100
            :return: True if vt100 characters are enabled for the handle
            """
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

            # Get the current mode for this handle in the console
            cur_mode = DWORD(0)
            readline.rl.console.GetConsoleMode(handle, byref(cur_mode))

            retVal = False

            # Check if ENABLE_VIRTUAL_TERMINAL_PROCESSING is already enabled
            if (cur_mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING) != 0:
                retVal = True

            elif readline.rl.console.SetConsoleMode(handle, cur_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING):
                # Restore the original mode when we exit
                atexit.register(readline.rl.console.SetConsoleMode, handle, cur_mode)
                retVal = True

            return retVal

        # Enable VT100 sequences for stdout and stderr
        STD_OUT_HANDLE = -11
        STD_ERROR_HANDLE = -12
        # noinspection PyUnresolvedReferences
        vt100_stdout_support = enable_win_vt100(readline.rl.console.GetStdHandle(STD_OUT_HANDLE))
        # noinspection PyUnresolvedReferences
        vt100_stderr_support = enable_win_vt100(readline.rl.console.GetStdHandle(STD_ERROR_HANDLE))
        vt100_support = vt100_stdout_support and vt100_stderr_support

    ############################################################################################################
    # pyreadline is incomplete in terms of the Python readline API. Add the missing functions we need.
    ############################################################################################################
    # readline.redisplay()
    try:
        getattr(readline, 'redisplay')
    except AttributeError:
        # noinspection PyProtectedMember,PyUnresolvedReferences
        readline.redisplay = readline.rl.mode._update_line

    # readline.remove_history_item()
    try:
        getattr(readline, 'remove_history_item')
    except AttributeError:
        # noinspection PyProtectedMember,PyUnresolvedReferences
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
        try:
            # Load the readline lib so we can access members of it
            import ctypes
            readline_lib = ctypes.CDLL(readline.__file__)
        except AttributeError:  # pragma: no cover
            _rl_warn_reason = ("this application is running in a non-standard Python environment in\n"
                               "which readline is not loaded dynamically from a shared library file.")
        else:
            rl_type = RlType.GNU
            vt100_support = sys.stdout.isatty()

# Check if readline was loaded
if rl_type == RlType.NONE:  # pragma: no cover
    if not _rl_warn_reason:
        _rl_warn_reason = ("no supported version of readline was found. To resolve this, install\n"
                           "pyreadline on Windows or gnureadline on Mac.")
    rl_warning = ("Readline features including tab completion have been disabled because\n"
                  + _rl_warn_reason + '\n\n')
else:
    rl_warning = ''


# noinspection PyProtectedMember,PyUnresolvedReferences
def rl_force_redisplay() -> None:  # pragma: no cover
    """
    Causes readline to display the prompt and input text wherever the cursor is and start
    reading input from this location. This is the proper way to restore the input line after
    printing to the screen
    """
    if not sys.stdout.isatty():
        return

    if rl_type == RlType.GNU:
        readline_lib.rl_forced_update_display()

        # After manually updating the display, readline asks that rl_display_fixed be set to 1 for efficiency
        display_fixed = ctypes.c_int.in_dll(readline_lib, "rl_display_fixed")
        display_fixed.value = 1

    elif rl_type == RlType.PYREADLINE:
        # Call _print_prompt() first to set the new location of the prompt
        readline.rl.mode._print_prompt()
        readline.rl.mode._update_line()


# noinspection PyProtectedMember, PyUnresolvedReferences
def rl_get_point() -> int:  # pragma: no cover
    """
    Returns the offset of the current cursor position in rl_line_buffer
    """
    if rl_type == RlType.GNU:
        return ctypes.c_int.in_dll(readline_lib, "rl_point").value

    elif rl_type == RlType.PYREADLINE:
        return readline.rl.mode.l_buffer.point

    else:
        return 0


# noinspection PyProtectedMember, PyUnresolvedReferences
def rl_set_prompt(prompt: str) -> None:  # pragma: no cover
    """
    Sets readline's prompt
    :param prompt: the new prompt value
    """
    safe_prompt = rl_make_safe_prompt(prompt)

    if rl_type == RlType.GNU:
        encoded_prompt = bytes(safe_prompt, encoding='utf-8')
        readline_lib.rl_set_prompt(encoded_prompt)

    elif rl_type == RlType.PYREADLINE:
        readline.rl._set_prompt(safe_prompt)


def rl_make_safe_prompt(prompt: str) -> str:  # pragma: no cover
    """Overcome bug in GNU Readline in relation to calculation of prompt length in presence of ANSI escape codes

    :param prompt: original prompt
    :return: prompt safe to pass to GNU Readline
    """
    if rl_type == RlType.GNU:
        # start code to tell GNU Readline about beginning of invisible characters
        start = "\x01"

        # end code to tell GNU Readline about end of invisible characters
        end = "\x02"

        escaped = False
        result = ""

        for c in prompt:
            if c == "\x1b" and not escaped:
                result += start + c
                escaped = True
            elif c.isalpha() and escaped:
                result += c + end
                escaped = False
            else:
                result += c

        return result

    else:
        return prompt
