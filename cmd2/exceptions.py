# coding=utf-8
"""Custom exceptions for cmd2.  These are NOT part of the public API and are intended for internal use only."""


class EmbeddedConsoleExit(SystemExit):
    """Custom exception class for use with the py command."""
    pass


class EmptyStatement(Exception):
    """Custom exception class for handling behavior when the user just presses <Enter>."""
    pass
