# coding=utf-8
"""Custom exceptions for cmd2.  These are NOT part of the public API and are intended for internal use only."""


class Cmd2ArgparseException(Exception):
    """Custom exception class for when an argparse-decorated command has an error parsing its arguments"""
    pass


class EmbeddedConsoleExit(SystemExit):
    """Custom exception class for use with the py command."""
    pass


class EmptyStatement(Exception):
    """Custom exception class for handling behavior when the user just presses <Enter>."""
    pass
