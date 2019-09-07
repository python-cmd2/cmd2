# coding=utf-8
"""
This module provides basic ability to copy from and paste to the clipboard/pastebuffer.
"""
import pyperclip
# noinspection PyProtectedMember
from pyperclip import PyperclipException

# Can we access the clipboard?  Should always be true on Windows and Mac, but only sometimes on Linux
try:
    # Try getting the contents of the clipboard
    _ = pyperclip.paste()
except (PyperclipException, FileNotFoundError, ValueError):
    # NOTE: FileNotFoundError is for Windows Subsystem for Linux (WSL) when Windows paths are removed from $PATH
    # NOTE: ValueError is for headless Linux systems without Gtk installed
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
