# coding=utf-8
"""Custom exceptions for cmd2"""


############################################################################################################
# The following exceptions are part of the public API
############################################################################################################

class SkipPostcommandHooks(Exception):
    """
    Custom exception class for when a command has a failure bad enough to skip post command
    hooks, but not bad enough to print the exception to the user.
    """
    pass


class Cmd2ArgparseError(SkipPostcommandHooks):
    """
    A ``SkipPostcommandHooks`` exception for when a command fails to parse its arguments.
    Normally argparse raises a SystemExit exception in these cases. To avoid stopping the command
    loop, catch the SystemExit and raise this instead. If you still need to run post command hooks
    after parsing fails, just return instead of raising an exception.
    """
    pass


class CommandSetRegistrationError(Exception):
    """
    Exception that can be thrown when an error occurs while a CommandSet is being added or removed
    from a cmd2 application.
    """
    pass

############################################################################################################
# The following exceptions are NOT part of the public API and are intended for internal use only.
############################################################################################################


class Cmd2ShlexError(Exception):
    """Raised when shlex fails to parse a command line string in StatementParser"""
    pass


class EmbeddedConsoleExit(SystemExit):
    """Custom exception class for use with the py command."""
    pass


class EmptyStatement(Exception):
    """Custom exception class for handling behavior when the user just presses <Enter>."""
    pass


class RedirectionError(Exception):
    """Custom exception class for when redirecting or piping output fails"""
    pass
