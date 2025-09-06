"""Provides string utility functions.

This module offers a collection of string utility functions built on the Rich library.
These utilities are designed to correctly handle strings with ANSI style sequences and
full-width characters (like those used in CJK languages).
"""

from rich.align import AlignMethod
from rich.style import StyleType
from rich.text import Text

from . import rich_utils as ru


def align(
    val: str,
    align: AlignMethod,
    width: int | None = None,
    character: str = " ",
) -> str:
    """Align string to a given width.

    There are convenience wrappers around this function: align_left(), align_center(), and align_right()

    :param val: string to align
    :param align: one of "left", "center", or "right".
    :param width: Desired width. Defaults to width of the terminal.
    :param character: Character to pad with. Defaults to " ".

    """
    if width is None:
        width = ru.console_width()

    text = Text.from_ansi(val)
    text.align(align, width=width, character=character)
    return ru.rich_text_to_string(text)


def align_left(
    val: str,
    width: int | None = None,
    character: str = " ",
) -> str:
    """Left-align string to a given width.

    :param val: string to align
    :param width: Desired width. Defaults to width of the terminal.
    :param character: Character to pad with. Defaults to " ".

    """
    return align(val, "left", width=width, character=character)


def align_center(
    val: str,
    width: int | None = None,
    character: str = " ",
) -> str:
    """Center-align string to a given width.

    :param val: string to align
    :param width: Desired width. Defaults to width of the terminal.
    :param character: Character to pad with. Defaults to " ".

    """
    return align(val, "center", width=width, character=character)


def align_right(
    val: str,
    width: int | None = None,
    character: str = " ",
) -> str:
    """Right-align string to a given width.

    :param val: string to align
    :param width: Desired width. Defaults to width of the terminal.
    :param character: Character to pad with. Defaults to " ".

    """
    return align(val, "right", width=width, character=character)


def stylize(val: str, style: StyleType) -> str:
    """Apply an ANSI style to a string, preserving any existing styles.

    :param val: string to be styled
    :param style: style instance or style definition to apply.
    :return: the stylized string
    """
    # Convert to a Rich Text object to parse and preserve existing ANSI styles.
    text = Text.from_ansi(val)
    text.stylize(style)
    return ru.rich_text_to_string(text)


def strip_style(val: str) -> str:
    """Strip all ANSI style sequences from a string.

    :param val: string to be stripped
    :return: the stripped string
    """
    return ru.ANSI_STYLE_SEQUENCE_RE.sub("", val)


def str_width(val: str) -> int:
    """Return the display width of a string.

    This is intended for single-line strings.
    Replace tabs with spaces before calling this.

    :param val: the string being measured
    :return: width of the string when printed to the terminal
    """
    text = Text.from_ansi(val)
    return text.cell_len


def is_quoted(val: str) -> bool:
    """Check if a string is quoted.

    :param val: the string being checked for quotes
    :return: True if a string is quoted
    """
    from . import constants

    return len(val) > 1 and val[0] == val[-1] and val[0] in constants.QUOTES


def quote(val: str) -> str:
    """Quote a string."""
    quote = "'" if '"' in val else '"'

    return quote + val + quote


def quote_if_needed(val: str) -> str:
    """Quote a string if it contains spaces and isn't already quoted."""
    if is_quoted(val) or ' ' not in val:
        return val

    return quote(val)


def strip_quotes(val: str) -> str:
    """Strip outer quotes from a string.

     Applies to both single and double quotes.

    :param val:  string to strip outer quotes from
    :return: same string with potentially outer quotes stripped
    """
    if is_quoted(val):
        val = val[1:-1]
    return val


def norm_fold(val: str) -> str:
    """Normalize and casefold Unicode strings for saner comparisons.

    :param val: input unicode string
    :return: a normalized and case-folded version of the input string
    """
    import unicodedata

    return unicodedata.normalize("NFC", val).casefold()
