# coding=utf-8
"""
This module provides basic ability to copy from and paste to the clipboard/pastebuffer.
"""
import sys

import pyperclip

# Newer versions of pyperclip are released as a single file, but older versions had a more complicated structure
try:
    from pyperclip.exceptions import PyperclipException
except ImportError:  # pragma: no cover
    # noinspection PyUnresolvedReferences,PyProtectedMember
    from pyperclip import PyperclipException

# Can we access the clipboard?  Should always be true on Windows and Mac, but only sometimes on Linux
# noinspection PyUnresolvedReferences
try:
    # Get the version of the pyperclip module as a float
    pyperclip_ver = float('.'.join(pyperclip.__version__.split('.')[:2]))

    # The extraneous output bug in pyperclip on Linux using xclip was fixed in more recent versions of pyperclip
    if sys.platform.startswith('linux') and pyperclip_ver < 1.6:
        # Avoid extraneous output to stderr from xclip when clipboard is empty at cost of overwriting clipboard contents
        pyperclip.copy('')
    else:
        # Try getting the contents of the clipboard
        _ = pyperclip.paste()
except PyperclipException:
    can_clip = False
else:
    can_clip = True


def get_paste_buffer() -> str:
    """Get the contents of the clipboard / paste buffer.

    :return: contents of the clipboard
    """
    pb_str = pyperclip.paste()
    return pb_str


def write_to_paste_buffer(txt: str) -> None:
    """Copy text to the clipboard / paste buffer.

    :param txt: text to copy to the clipboard
    """
    pyperclip.copy(txt)
