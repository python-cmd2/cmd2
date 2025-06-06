"""Imports the proper Readline for the platform and provides utility functions for it."""

import contextlib
import sys
from enum import (
    Enum,
)
from typing import Union

#########################################################################################################################
# NOTE ON LIBEDIT:
#
# On Linux/Mac, the underlying readline API may be implemented by libedit instead of GNU readline.
# We don't support libedit because it doesn't implement all the readline features cmd2 needs.
#
# For example:
#     cmd2 sets a custom display function using Python's readline.set_completion_display_matches_hook() to
#     support many of its advanced tab completion features (e.g. tab completion tables, displaying path basenames,
#     colored results, etc.). This function "sets or clears the rl_completion_display_matches_hook callback in the
#     underlying library". libedit has never implemented rl_completion_display_matches_hook. It merely sets it to NULL
#     and never references it.
#
# The workaround for Python environments using libedit is to install the gnureadline Python library.
#########################################################################################################################

# Prefer statically linked gnureadline if installed due to compatibility issues with libedit
try:
    import gnureadline as readline  # type: ignore[import]
except ImportError:
    # Note: If this actually fails, you should install gnureadline on Linux/Mac or pyreadline3 on Windows.
    with contextlib.suppress(ImportError):
        import readline  # type: ignore[no-redef]


class RlType(Enum):
    """Readline library types we support."""

    GNU = 1
    PYREADLINE = 2
    NONE = 3


# Check what implementation of Readline we are using
rl_type = RlType.NONE

# Tells if the terminal we are running in supports vt100 control characters
vt100_support = False

# Explanation for why Readline wasn't loaded
_rl_warn_reason = ''

# The order of this check matters since importing pyreadline3 will also show readline in the modules list
if 'pyreadline3' in sys.modules:
    rl_type = RlType.PYREADLINE

    import atexit
    from ctypes import (
        byref,
    )
    from ctypes.wintypes import (
        DWORD,
        HANDLE,
    )

    # Check if we are running in a terminal
    if sys.stdout is not None and sys.stdout.isatty():  # pragma: no cover

        def enable_win_vt100(handle: HANDLE) -> bool:
            """Enable VT100 character sequences in a Windows console.

            This only works on Windows 10 and up
            :param handle: the handle on which to enable vt100
            :return: True if vt100 characters are enabled for the handle.
            """
            enable_virtual_terminal_processing = 0x0004

            # Get the current mode for this handle in the console
            cur_mode = DWORD(0)
            readline.rl.console.GetConsoleMode(handle, byref(cur_mode))

            ret_val = False

            # Check if ENABLE_VIRTUAL_TERMINAL_PROCESSING is already enabled
            if (cur_mode.value & enable_virtual_terminal_processing) != 0:
                ret_val = True

            elif readline.rl.console.SetConsoleMode(handle, cur_mode.value | enable_virtual_terminal_processing):
                # Restore the original mode when we exit
                atexit.register(readline.rl.console.SetConsoleMode, handle, cur_mode)
                ret_val = True

            return ret_val

        # Enable VT100 sequences for stdout and stderr
        STD_OUT_HANDLE = -11
        STD_ERROR_HANDLE = -12
        vt100_stdout_support = enable_win_vt100(readline.rl.console.GetStdHandle(STD_OUT_HANDLE))
        vt100_stderr_support = enable_win_vt100(readline.rl.console.GetStdHandle(STD_ERROR_HANDLE))
        vt100_support = vt100_stdout_support and vt100_stderr_support

    ############################################################################################################
    # pyreadline3 is incomplete in terms of the Python readline API. Add the missing functions we need.
    ############################################################################################################
    # Add missing `readline.remove_history_item()`
    if not hasattr(readline, 'remove_history_item'):

        def pyreadline_remove_history_item(pos: int) -> None:
            """Remove the specified item number from the pyreadline3 history.

            An implementation of remove_history_item() for pyreadline3.

            :param pos: The 0-based position in history to remove.
            """
            # Save of the current location of the history cursor
            saved_cursor = readline.rl.mode._history.history_cursor

            # Delete the history item
            del readline.rl.mode._history.history[pos]

            # Update the cursor if needed
            if saved_cursor > pos:
                readline.rl.mode._history.history_cursor -= 1

        readline.remove_history_item = pyreadline_remove_history_item

elif 'gnureadline' in sys.modules or 'readline' in sys.modules:
    # We don't support libedit. See top of this file for why.
    if readline.__doc__ is not None and 'libedit' not in readline.__doc__:
        try:
            # Load the readline lib so we can access members of it
            import ctypes

            readline_lib = ctypes.CDLL(readline.__file__)
        except (AttributeError, OSError):  # pragma: no cover
            _rl_warn_reason = (
                "this application is running in a non-standard Python environment in\n"
                "which GNU readline is not loaded dynamically from a shared library file."
            )
        else:
            rl_type = RlType.GNU
            vt100_support = sys.stdout.isatty()

# Check if we loaded a supported version of readline
if rl_type == RlType.NONE:  # pragma: no cover
    if not _rl_warn_reason:
        _rl_warn_reason = (
            "no supported version of readline was found. To resolve this, install\n"
            "pyreadline3 on Windows or gnureadline on Linux/Mac."
        )
    rl_warning = "Readline features including tab completion have been disabled because\n" + _rl_warn_reason + '\n\n'
else:
    rl_warning = ''


def rl_force_redisplay() -> None:  # pragma: no cover
    """Causes readline to display the prompt and input text wherever the cursor is and start reading input from this location.

    This is the proper way to restore the input line after printing to the screen.
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


def rl_get_point() -> int:  # pragma: no cover
    """Return the offset of the current cursor position in rl_line_buffer."""
    if rl_type == RlType.GNU:
        return ctypes.c_int.in_dll(readline_lib, "rl_point").value

    if rl_type == RlType.PYREADLINE:
        return int(readline.rl.mode.l_buffer.point)

    return 0


def rl_get_prompt() -> str:  # pragma: no cover
    """Get Readline's prompt."""
    if rl_type == RlType.GNU:
        encoded_prompt = ctypes.c_char_p.in_dll(readline_lib, "rl_prompt").value
        prompt = '' if encoded_prompt is None else encoded_prompt.decode(encoding='utf-8')

    elif rl_type == RlType.PYREADLINE:
        prompt_data: Union[str, bytes] = readline.rl.prompt
        prompt = prompt_data.decode(encoding='utf-8') if isinstance(prompt_data, bytes) else prompt_data

    else:
        prompt = ''

    return rl_unescape_prompt(prompt)


def rl_get_display_prompt() -> str:  # pragma: no cover
    """Get Readline's currently displayed prompt.

    In GNU Readline, the displayed prompt sometimes differs from the prompt.
    This occurs in functions that use the prompt string as a message area, such as incremental search.
    """
    if rl_type == RlType.GNU:
        encoded_prompt = ctypes.c_char_p.in_dll(readline_lib, "rl_display_prompt").value
        prompt = '' if encoded_prompt is None else encoded_prompt.decode(encoding='utf-8')
        return rl_unescape_prompt(prompt)
    return rl_get_prompt()


def rl_set_prompt(prompt: str) -> None:  # pragma: no cover
    """Set Readline's prompt.

    :param prompt: the new prompt value.
    """
    escaped_prompt = rl_escape_prompt(prompt)

    if rl_type == RlType.GNU:
        encoded_prompt = bytes(escaped_prompt, encoding='utf-8')
        readline_lib.rl_set_prompt(encoded_prompt)

    elif rl_type == RlType.PYREADLINE:
        readline.rl.prompt = escaped_prompt


def rl_escape_prompt(prompt: str) -> str:
    """Overcome bug in GNU Readline in relation to calculation of prompt length in presence of ANSI escape codes.

    :param prompt: original prompt
    :return: prompt safe to pass to GNU Readline
    """
    if rl_type == RlType.GNU:
        # start code to tell GNU Readline about beginning of invisible characters
        escape_start = "\x01"

        # end code to tell GNU Readline about end of invisible characters
        escape_end = "\x02"

        escaped = False
        result = ""

        for c in prompt:
            if c == "\x1b" and not escaped:
                result += escape_start + c
                escaped = True
            elif c.isalpha() and escaped:
                result += c + escape_end
                escaped = False
            else:
                result += c

        return result

    return prompt


def rl_unescape_prompt(prompt: str) -> str:
    """Remove escape characters from a Readline prompt."""
    if rl_type == RlType.GNU:
        escape_start = "\x01"
        escape_end = "\x02"
        prompt = prompt.replace(escape_start, "").replace(escape_end, "")

    return prompt


def rl_in_search_mode() -> bool:  # pragma: no cover
    """Check if readline is doing either an incremental (e.g. Ctrl-r) or non-incremental (e.g. Esc-p) search."""
    if rl_type == RlType.GNU:
        # GNU Readline defines constants that we can use to determine if in search mode.
        #     RL_STATE_ISEARCH    0x0000080
        #     RL_STATE_NSEARCH    0x0000100
        in_search_mode = 0x0000180

        readline_state = ctypes.c_int.in_dll(readline_lib, "rl_readline_state").value
        return bool(in_search_mode & readline_state)
    if rl_type == RlType.PYREADLINE:
        from pyreadline3.modes.emacs import (  # type: ignore[import]
            EmacsMode,
        )

        # These search modes only apply to Emacs mode, which is the default.
        if not isinstance(readline.rl.mode, EmacsMode):
            return False

        # While in search mode, the current keyevent function is set one of the following.
        search_funcs = (
            readline.rl.mode._process_incremental_search_keyevent,
            readline.rl.mode._process_non_incremental_search_keyevent,
        )
        return readline.rl.mode.process_keyevent_queue[-1] in search_funcs
    return False
