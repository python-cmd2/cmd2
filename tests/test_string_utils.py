"""Unit testing for cmd2/string_utils.py module"""

from rich.style import Style

from cmd2 import Color
from cmd2 import rich_utils as ru
from cmd2 import string_utils as su

HELLO_WORLD = 'Hello, world!'


def test_align_blank() -> None:
    text = ''
    character = '-'
    width = 5
    aligned = su.align(text, "left", width=width, character=character)
    assert aligned == character * width


def test_align_wider_than_width() -> None:
    text = 'long text field'
    character = '-'
    width = 8
    aligned = su.align(text, "left", width=width, character=character)
    assert aligned == text[:width]


def test_align_term_width() -> None:
    text = 'foo'
    character = ' '

    term_width = ru.console_width()
    expected_padding = (term_width - su.str_width(text)) * character

    aligned = su.align(text, "left", character=character)
    assert aligned == text + expected_padding


def test_align_left() -> None:
    text = 'foo'
    character = '-'
    width = 5
    aligned = su.align_left(text, width=width, character=character)
    assert aligned == text + character * 2


def test_align_left_wide_text() -> None:
    text = '苹'
    character = '-'
    width = 4
    aligned = su.align_left(text, width=width, character=character)
    assert aligned == text + character * 2


def test_align_left_with_style() -> None:
    character = '-'

    styled_text = su.stylize('table', style=Color.BRIGHT_BLUE)
    width = 8

    aligned = su.align_left(styled_text, width=width, character=character)
    assert aligned == styled_text + character * 3


def test_align_center() -> None:
    text = 'foo'
    character = '-'
    width = 5
    aligned = su.align_center(text, width=width, character=character)
    assert aligned == character + text + character


def test_align_center_wide_text() -> None:
    text = '苹'
    character = '-'
    width = 4
    aligned = su.align_center(text, width=width, character=character)
    assert aligned == character + text + character


def test_align_center_with_style() -> None:
    character = '-'

    styled_text = su.stylize('table', style=Color.BRIGHT_BLUE)
    width = 8

    aligned = su.align_center(styled_text, width=width, character=character)
    assert aligned == character + styled_text + character * 2


def test_align_right() -> None:
    text = 'foo'
    character = '-'
    width = 5
    aligned = su.align_right(text, width=width, character=character)
    assert aligned == character * 2 + text


def test_align_right_wide_text() -> None:
    text = '苹'
    character = '-'
    width = 4
    aligned = su.align_right(text, width=width, character=character)
    assert aligned == character * 2 + text


def test_align_right_with_style() -> None:
    character = '-'

    styled_text = su.stylize('table', style=Color.BRIGHT_BLUE)
    width = 8

    aligned = su.align_right(styled_text, width=width, character=character)
    assert aligned == character * 3 + styled_text


def test_stylize() -> None:
    # Test string with no existing style
    style = Style(color=Color.GREEN, bgcolor=Color.BLUE, bold=True, underline=True)
    styled_str = su.stylize(HELLO_WORLD, style=style)
    assert styled_str == "\x1b[1;4;32;44mHello, world!\x1b[0m"

    # Add style to already-styled string
    updated_style = Style.combine([style, Style(strike=True)])
    restyled_string = su.stylize(styled_str, style=updated_style)
    assert restyled_string == "\x1b[1;4;9;32;44mHello, world!\x1b[0m"


def test_strip_style() -> None:
    base_str = HELLO_WORLD
    styled_str = su.stylize(base_str, style=Color.GREEN)
    assert base_str != styled_str
    assert base_str == su.strip_style(styled_str)


def test_str_width() -> None:
    # Include a full-width character
    base_str = HELLO_WORLD + "深"
    styled_str = su.stylize(base_str, style=Color.GREEN)
    expected_width = len(HELLO_WORLD) + 2
    assert su.str_width(base_str) == su.str_width(styled_str) == expected_width


def test_is_quoted_short() -> None:
    my_str = ''
    assert not su.is_quoted(my_str)
    your_str = '"'
    assert not su.is_quoted(your_str)


def test_is_quoted_yes() -> None:
    my_str = '"This is a test"'
    assert su.is_quoted(my_str)
    your_str = "'of the emergengy broadcast system'"
    assert su.is_quoted(your_str)


def test_is_quoted_no() -> None:
    my_str = '"This is a test'
    assert not su.is_quoted(my_str)
    your_str = "of the emergengy broadcast system'"
    assert not su.is_quoted(your_str)
    simple_str = "hello world"
    assert not su.is_quoted(simple_str)


def test_quote() -> None:
    my_str = "Hello World"
    assert su.quote(my_str) == '"' + my_str + '"'

    my_str = "'Hello World'"
    assert su.quote(my_str) == '"' + my_str + '"'

    my_str = '"Hello World"'
    assert su.quote(my_str) == "'" + my_str + "'"


def test_quote_if_needed_yes() -> None:
    my_str = "Hello World"
    assert su.quote_if_needed(my_str) == '"' + my_str + '"'
    your_str = '"foo" bar'
    assert su.quote_if_needed(your_str) == "'" + your_str + "'"


def test_quote_if_needed_no() -> None:
    my_str = "HelloWorld"
    assert su.quote_if_needed(my_str) == my_str
    your_str = "'Hello World'"
    assert su.quote_if_needed(your_str) == your_str


def test_strip_quotes_no_quotes() -> None:
    base_str = HELLO_WORLD
    stripped = su.strip_quotes(base_str)
    assert base_str == stripped


def test_strip_quotes_with_quotes() -> None:
    base_str = '"' + HELLO_WORLD + '"'
    stripped = su.strip_quotes(base_str)
    assert stripped == HELLO_WORLD


def test_unicode_normalization() -> None:
    s1 = 'café'
    s2 = 'cafe\u0301'
    assert s1 != s2
    assert su.norm_fold(s1) == su.norm_fold(s2)


def test_unicode_casefold() -> None:
    micro = 'µ'
    micro_cf = micro.casefold()
    assert micro != micro_cf
    assert su.norm_fold(micro) == su.norm_fold(micro_cf)
