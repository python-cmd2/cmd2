"""Module provides basic ability to copy from and paste to the clipboard/pastebuffer."""

import typing

import pyperclip  # type: ignore[import-untyped]


def get_paste_buffer() -> str:
    """Get the contents of the clipboard / paste buffer.

    :return: contents of the clipboard
    """
    return typing.cast(str, pyperclip.paste())


def write_to_paste_buffer(txt: str) -> None:
    """Copy text to the clipboard / paste buffer.

    :param txt: text to copy to the clipboard
    """
    pyperclip.copy(txt)
