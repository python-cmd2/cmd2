# coding=utf-8
"""
This module provides basic ability to copy from and paste to the clipboard/pastebuffer.
"""

import typing

import pyperclip  # type: ignore[import]


def get_paste_buffer() -> str:
    """Get the contents of the clipboard / paste buffer.

    :return: contents of the clipboard
    """
    pb_str = typing.cast(str, pyperclip.paste())
    return pb_str


def write_to_paste_buffer(txt: str) -> None:
    """Copy text to the clipboard / paste buffer.

    :param txt: text to copy to the clipboard
    """
    pyperclip.copy(txt)
