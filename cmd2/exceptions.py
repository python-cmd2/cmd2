# coding=utf-8
"""Custom exceptions for cmd2.  These are NOT part of the public API and are intended for internal use only."""


class Cmd2ArgparseError(Exception):
    """
    Custom exception class for when a command has an error parsing its arguments.
    This can be raised by argparse decorators or the command functions themselves.
    The main use of this exception is to tell cmd2 not to run Postcommand hooks.
    """
    pass


class Cmd2ShlexError(Exception):
    """Raised when shlex fails to parse a command line string in StatementParser"""
    pass


class EmbeddedConsoleExit(SystemExit):
    """Custom exception class for use with the py command."""
    pass


class EmptyStatement(Exception):
    """Custom exception class for handling behavior when the user just presses <Enter>."""
    pass
