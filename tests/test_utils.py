"""Unit testing for cmd2/utils.py module."""

import os
import signal
import sys
import time
from unittest import (
    mock,
)

import pytest

import cmd2.utils as cu
from cmd2 import (
    ansi,
    constants,
)
from cmd2.constants import (
    HORIZONTAL_ELLIPSIS,
)

HELLO_WORLD = 'Hello, world!'


def test_strip_quotes_no_quotes() -> None:
    base_str = HELLO_WORLD
    stripped = cu.strip_quotes(base_str)
    assert base_str == stripped


def test_strip_quotes_with_quotes() -> None:
    base_str = '"' + HELLO_WORLD + '"'
    stripped = cu.strip_quotes(base_str)
    assert stripped == HELLO_WORLD


def test_remove_duplicates_no_duplicates() -> None:
    no_dups = [5, 4, 3, 2, 1]
    assert cu.remove_duplicates(no_dups) == no_dups


def test_remove_duplicates_with_duplicates() -> None:
    duplicates = [1, 1, 2, 3, 9, 9, 7, 8]
    assert cu.remove_duplicates(duplicates) == [1, 2, 3, 9, 7, 8]


def test_unicode_normalization() -> None:
    s1 = 'café'
    s2 = 'cafe\u0301'
    assert s1 != s2
    assert cu.norm_fold(s1) == cu.norm_fold(s2)


def test_unicode_casefold() -> None:
    micro = 'µ'
    micro_cf = micro.casefold()
    assert micro != micro_cf
    assert cu.norm_fold(micro) == cu.norm_fold(micro_cf)


def test_alphabetical_sort() -> None:
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'cafeteria']
    assert cu.alphabetical_sort(my_list) == ['A', 'cafeteria', 'café', 'micro', 'unity', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.alphabetical_sort(my_list) == ['a1', 'A11', 'A2', 'a22', 'a3']


def test_try_int_or_force_to_lower_case() -> None:
    str1 = '17'
    assert cu.try_int_or_force_to_lower_case(str1) == 17
    str1 = 'ABC'
    assert cu.try_int_or_force_to_lower_case(str1) == 'abc'
    str1 = 'X19'
    assert cu.try_int_or_force_to_lower_case(str1) == 'x19'
    str1 = ''
    assert cu.try_int_or_force_to_lower_case(str1) == ''


def test_natural_keys() -> None:
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['a1', 'A2', 'a3', 'A11', 'a22']


def test_natural_sort() -> None:
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    assert cu.natural_sort(my_list) == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.natural_sort(my_list) == ['a1', 'A2', 'a3', 'A11', 'a22']


def test_is_quoted_short() -> None:
    my_str = ''
    assert not cu.is_quoted(my_str)
    your_str = '"'
    assert not cu.is_quoted(your_str)


def test_is_quoted_yes() -> None:
    my_str = '"This is a test"'
    assert cu.is_quoted(my_str)
    your_str = "'of the emergengy broadcast system'"
    assert cu.is_quoted(your_str)


def test_is_quoted_no() -> None:
    my_str = '"This is a test'
    assert not cu.is_quoted(my_str)
    your_str = "of the emergengy broadcast system'"
    assert not cu.is_quoted(your_str)
    simple_str = "hello world"
    assert not cu.is_quoted(simple_str)


def test_quote_string() -> None:
    my_str = "Hello World"
    assert cu.quote_string(my_str) == '"' + my_str + '"'

    my_str = "'Hello World'"
    assert cu.quote_string(my_str) == '"' + my_str + '"'

    my_str = '"Hello World"'
    assert cu.quote_string(my_str) == "'" + my_str + "'"


def test_quote_string_if_needed_yes() -> None:
    my_str = "Hello World"
    assert cu.quote_string_if_needed(my_str) == '"' + my_str + '"'
    your_str = '"foo" bar'
    assert cu.quote_string_if_needed(your_str) == "'" + your_str + "'"


def test_quote_string_if_needed_no() -> None:
    my_str = "HelloWorld"
    assert cu.quote_string_if_needed(my_str) == my_str
    your_str = "'Hello World'"
    assert cu.quote_string_if_needed(your_str) == your_str


@pytest.fixture
def stdout_sim():
    return cu.StdSim(sys.stdout, echo=True)


def test_stdsim_write_str(stdout_sim) -> None:
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str


def test_stdsim_write_bytes(stdout_sim) -> None:
    b_str = b'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.write(b_str)


def test_stdsim_buffer_write_bytes(stdout_sim) -> None:
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getvalue() == b_str.decode()
    assert stdout_sim.getbytes() == b_str


def test_stdsim_buffer_write_str(stdout_sim) -> None:
    my_str = 'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.buffer.write(my_str)


def test_stdsim_read(stdout_sim) -> None:
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    # getvalue() returns the value and leaves it unaffected internally
    assert stdout_sim.getvalue() == my_str
    # read() returns the value and then clears the internal buffer
    assert stdout_sim.read() == my_str
    assert stdout_sim.getvalue() == ''

    stdout_sim.write(my_str)

    assert stdout_sim.getvalue() == my_str
    assert stdout_sim.read(2) == my_str[:2]
    assert stdout_sim.getvalue() == my_str[2:]


def test_stdsim_read_bytes(stdout_sim) -> None:
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    # getbytes() returns the value and leaves it unaffected internally
    assert stdout_sim.getbytes() == b_str
    # read_bytes() returns the value and then clears the internal buffer
    assert stdout_sim.readbytes() == b_str
    assert stdout_sim.getbytes() == b''


def test_stdsim_clear(stdout_sim) -> None:
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str
    stdout_sim.clear()
    assert stdout_sim.getvalue() == ''


def test_stdsim_getattr_exist(stdout_sim) -> None:
    # Here the StdSim getattr is allowing us to access methods within StdSim
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    val_func = stdout_sim.getvalue
    assert val_func() == my_str


def test_stdsim_getattr_noexist(stdout_sim) -> None:
    # Here the StdSim getattr is allowing us to access methods defined by the inner stream
    assert not stdout_sim.isatty()


def test_stdsim_pause_storage(stdout_sim) -> None:
    # Test pausing storage for string data
    my_str = 'Hello World'

    stdout_sim.pause_storage = False
    stdout_sim.write(my_str)
    assert stdout_sim.read() == my_str

    stdout_sim.pause_storage = True
    stdout_sim.write(my_str)
    assert stdout_sim.read() == ''

    # Test pausing storage for binary data
    b_str = b'Hello World'

    stdout_sim.pause_storage = False
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.readbytes() == b_str

    stdout_sim.pause_storage = True
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getbytes() == b''


def test_stdsim_line_buffering(base_app) -> None:
    # This exercises the case of writing binary data that contains new lines/carriage returns to a StdSim
    # when line buffering is on. The output should immediately be flushed to the underlying stream.
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode='wt') as file:
        file.line_buffering = True

        stdsim = cu.StdSim(file, echo=True)
        saved_size = os.path.getsize(file.name)

        bytes_to_write = b'hello\n'
        stdsim.buffer.write(bytes_to_write)
        assert os.path.getsize(file.name) == saved_size + len(bytes_to_write)
        saved_size = os.path.getsize(file.name)

        bytes_to_write = b'hello\r'
        stdsim.buffer.write(bytes_to_write)
        assert os.path.getsize(file.name) == saved_size + len(bytes_to_write)


@pytest.fixture
def pr_none():
    import subprocess

    # Start a long running process so we have time to run tests on it before it finishes
    # Put the new process into a separate group so its signal are isolated from ours
    kwargs = {}
    if sys.platform.startswith('win'):
        command = 'timeout -t 5 /nobreak'
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        command = 'sleep 5'
        kwargs['start_new_session'] = True

    proc = subprocess.Popen(command, shell=True, **kwargs)
    return cu.ProcReader(proc, None, None)


def test_proc_reader_send_sigint(pr_none) -> None:
    assert pr_none._proc.poll() is None
    pr_none.send_sigint()
    pr_none.wait()
    ret_code = pr_none._proc.poll()

    # Make sure a SIGINT killed the process
    if sys.platform.startswith('win'):
        assert ret_code is not None
    else:
        assert ret_code == -signal.SIGINT


def test_proc_reader_terminate(pr_none) -> None:
    assert pr_none._proc.poll() is None
    pr_none.terminate()

    wait_start = time.monotonic()
    pr_none.wait()
    wait_finish = time.monotonic()

    # Make sure the process exited before sleep of 5 seconds finished
    # 3 seconds accounts for some delay but is long enough for the process to exit
    assert wait_finish - wait_start < 3

    ret_code = pr_none._proc.poll()
    if sys.platform.startswith('win'):
        assert ret_code is not None
    else:
        assert ret_code == -signal.SIGTERM


@pytest.fixture
def context_flag():
    return cu.ContextFlag()


def test_context_flag_bool(context_flag) -> None:
    assert not context_flag
    with context_flag:
        assert context_flag


def test_context_flag_exit_err(context_flag) -> None:
    with pytest.raises(ValueError, match="count has gone below 0"):
        context_flag.__exit__()


def test_remove_overridden_styles() -> None:
    from cmd2 import (
        Bg,
        EightBitBg,
        EightBitFg,
        Fg,
        RgbBg,
        RgbFg,
        TextStyle,
    )

    def make_strs(styles_list: list[ansi.AnsiSequence]) -> list[str]:
        return [str(s) for s in styles_list]

    # Test Reset All
    styles_to_parse = make_strs([Fg.BLUE, TextStyle.UNDERLINE_DISABLE, TextStyle.INTENSITY_DIM, TextStyle.RESET_ALL])
    expected = make_strs([TextStyle.RESET_ALL])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([Fg.BLUE, TextStyle.UNDERLINE_DISABLE, TextStyle.INTENSITY_DIM, TextStyle.ALT_RESET_ALL])
    expected = make_strs([TextStyle.ALT_RESET_ALL])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    # Test colors
    styles_to_parse = make_strs([Fg.BLUE, Fg.RED, Fg.GREEN, Bg.BLUE, Bg.RED, Bg.GREEN])
    expected = make_strs([Fg.GREEN, Bg.GREEN])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([EightBitFg.BLUE, EightBitFg.RED, EightBitBg.BLUE, EightBitBg.RED])
    expected = make_strs([EightBitFg.RED, EightBitBg.RED])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([RgbFg(0, 3, 4), RgbFg(5, 6, 7), RgbBg(8, 9, 10), RgbBg(11, 12, 13)])
    expected = make_strs([RgbFg(5, 6, 7), RgbBg(11, 12, 13)])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    # Test text styles
    styles_to_parse = make_strs([TextStyle.INTENSITY_DIM, TextStyle.INTENSITY_NORMAL, TextStyle.ITALIC_ENABLE])
    expected = make_strs([TextStyle.INTENSITY_NORMAL, TextStyle.ITALIC_ENABLE])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([TextStyle.INTENSITY_DIM, TextStyle.ITALIC_ENABLE, TextStyle.ITALIC_DISABLE])
    expected = make_strs([TextStyle.INTENSITY_DIM, TextStyle.ITALIC_DISABLE])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([TextStyle.INTENSITY_BOLD, TextStyle.OVERLINE_DISABLE, TextStyle.OVERLINE_ENABLE])
    expected = make_strs([TextStyle.INTENSITY_BOLD, TextStyle.OVERLINE_ENABLE])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([TextStyle.OVERLINE_DISABLE, TextStyle.STRIKETHROUGH_DISABLE, TextStyle.STRIKETHROUGH_ENABLE])
    expected = make_strs([TextStyle.OVERLINE_DISABLE, TextStyle.STRIKETHROUGH_ENABLE])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([TextStyle.STRIKETHROUGH_DISABLE, TextStyle.UNDERLINE_DISABLE, TextStyle.UNDERLINE_ENABLE])
    expected = make_strs([TextStyle.STRIKETHROUGH_DISABLE, TextStyle.UNDERLINE_ENABLE])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    styles_to_parse = make_strs([TextStyle.UNDERLINE_DISABLE])
    expected = make_strs([TextStyle.UNDERLINE_DISABLE])
    assert cu._remove_overridden_styles(styles_to_parse) == expected

    # Test unrecognized styles
    slow_blink = ansi.CSI + str(5)
    rapid_blink = ansi.CSI + str(6)
    styles_to_parse = [slow_blink, rapid_blink]
    expected = styles_to_parse
    assert cu._remove_overridden_styles(styles_to_parse) == expected


def test_truncate_line() -> None:
    line = 'long'
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == 'lo' + HORIZONTAL_ELLIPSIS


def test_truncate_line_already_fits() -> None:
    line = 'long'
    max_width = 4
    truncated = cu.truncate_line(line, max_width)
    assert truncated == line


def test_truncate_line_with_newline() -> None:
    line = 'fo\no'
    max_width = 2
    with pytest.raises(ValueError, match="text contains an unprintable character"):
        cu.truncate_line(line, max_width)


def test_truncate_line_width_is_too_small() -> None:
    line = 'foo'
    max_width = 0
    with pytest.raises(ValueError, match="max_width must be at least 1"):
        cu.truncate_line(line, max_width)


def test_truncate_line_wide_text() -> None:
    line = '苹苹other'
    max_width = 6
    truncated = cu.truncate_line(line, max_width)
    assert truncated == '苹苹o' + HORIZONTAL_ELLIPSIS


def test_truncate_line_split_wide_text() -> None:
    """Test when truncation results in a string which is shorter than max_width"""
    line = '1苹2苹'
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == '1' + HORIZONTAL_ELLIPSIS


def test_truncate_line_tabs() -> None:
    line = 'has\ttab'
    max_width = 9
    truncated = cu.truncate_line(line, max_width)
    assert truncated == 'has    t' + HORIZONTAL_ELLIPSIS


def test_truncate_with_style() -> None:
    from cmd2 import (
        Fg,
        TextStyle,
    )

    before_text = Fg.BLUE + TextStyle.UNDERLINE_ENABLE
    after_text = Fg.RESET + TextStyle.UNDERLINE_DISABLE + TextStyle.ITALIC_ENABLE + TextStyle.ITALIC_DISABLE

    # This is what the styles after the truncated text should look like since they will be
    # filtered by _remove_overridden_styles.
    filtered_after_text = Fg.RESET + TextStyle.UNDERLINE_DISABLE + TextStyle.ITALIC_DISABLE

    # Style only before truncated text
    line = before_text + 'long'
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == before_text + 'lo' + HORIZONTAL_ELLIPSIS

    # Style before and after truncated text
    line = before_text + 'long' + after_text
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == before_text + 'lo' + HORIZONTAL_ELLIPSIS + filtered_after_text

    # Style only after truncated text
    line = 'long' + after_text
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == 'lo' + HORIZONTAL_ELLIPSIS + filtered_after_text


def test_align_text_fill_char_is_tab() -> None:
    text = 'foo'
    fill_char = '\t'
    width = 5
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)
    assert aligned == text + '  '


def test_align_text_with_style() -> None:
    from cmd2 import (
        Fg,
        TextStyle,
        style,
    )

    fill_char = '-'
    styled_fill_char = style(fill_char, fg=Fg.LIGHT_YELLOW)

    # Single line with only left fill
    text = style('line1', fg=Fg.LIGHT_BLUE)
    width = 8

    aligned = cu.align_text(text, cu.TextAlignment.RIGHT, fill_char=styled_fill_char, width=width)

    left_fill = TextStyle.RESET_ALL + Fg.LIGHT_YELLOW + (fill_char * 3) + Fg.RESET + TextStyle.RESET_ALL
    right_fill = TextStyle.RESET_ALL
    line_1_text = Fg.LIGHT_BLUE + 'line1' + Fg.RESET

    assert aligned == (left_fill + line_1_text + right_fill)

    # Single line with only right fill
    text = style('line1', fg=Fg.LIGHT_BLUE)
    width = 8

    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=styled_fill_char, width=width)

    left_fill = TextStyle.RESET_ALL
    right_fill = TextStyle.RESET_ALL + Fg.LIGHT_YELLOW + (fill_char * 3) + Fg.RESET + TextStyle.RESET_ALL
    line_1_text = Fg.LIGHT_BLUE + 'line1' + Fg.RESET

    assert aligned == (left_fill + line_1_text + right_fill)

    # Multiple lines to show that style is preserved across all lines. Also has left and right fill.
    text = style('line1\nline2', fg=Fg.LIGHT_BLUE)
    width = 9

    aligned = cu.align_text(text, cu.TextAlignment.CENTER, fill_char=styled_fill_char, width=width)

    left_fill = TextStyle.RESET_ALL + Fg.LIGHT_YELLOW + (fill_char * 2) + Fg.RESET + TextStyle.RESET_ALL
    right_fill = TextStyle.RESET_ALL + Fg.LIGHT_YELLOW + (fill_char * 2) + Fg.RESET + TextStyle.RESET_ALL
    line_1_text = Fg.LIGHT_BLUE + 'line1'
    line_2_text = Fg.LIGHT_BLUE + 'line2' + Fg.RESET

    assert aligned == (left_fill + line_1_text + right_fill + '\n' + left_fill + line_2_text + right_fill)


def test_align_text_width_is_too_small() -> None:
    text = 'foo'
    fill_char = '-'
    width = 0
    with pytest.raises(ValueError, match="width must be at least 1"):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)


def test_align_text_fill_char_is_too_long() -> None:
    text = 'foo'
    fill_char = 'fill'
    width = 5
    with pytest.raises(TypeError):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)


def test_align_text_fill_char_is_newline() -> None:
    text = 'foo'
    fill_char = '\n'
    width = 5
    with pytest.raises(ValueError, match="Fill character is an unprintable character"):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)


def test_align_text_has_tabs() -> None:
    text = '\t\tfoo'
    fill_char = '-'
    width = 10
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width, tab_width=2)
    assert aligned == '    ' + 'foo' + '---'


def test_align_text_blank() -> None:
    text = ''
    fill_char = '-'
    width = 5
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)
    assert aligned == fill_char * width


def test_align_text_wider_than_width() -> None:
    text = 'long text field'
    fill_char = '-'
    width = 8
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)
    assert aligned == text


def test_align_text_wider_than_width_truncate() -> None:
    text = 'long text field'
    fill_char = '-'
    width = 8
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width, truncate=True)
    assert aligned == 'long te' + HORIZONTAL_ELLIPSIS


def test_align_text_wider_than_width_truncate_add_fill() -> None:
    """Test when truncation results in a string which is shorter than width and align_text adds filler"""
    text = '1苹2苹'
    fill_char = '-'
    width = 3
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width, truncate=True)
    assert aligned == '1' + HORIZONTAL_ELLIPSIS + fill_char


def test_align_text_has_unprintable() -> None:
    text = 'foo\x02'
    fill_char = '-'
    width = 5
    with pytest.raises(ValueError, match="Text to align contains an unprintable character"):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)


def test_align_text_term_width() -> None:
    import shutil

    text = 'foo'
    fill_char = ' '

    # Prior to Python 3.11 this can return 0, so use a fallback, so
    # use the same fallback that cu.align_text() does if needed.
    term_width = shutil.get_terminal_size().columns or constants.DEFAULT_TERMINAL_WIDTH
    expected_fill = (term_width - ansi.style_aware_wcswidth(text)) * fill_char

    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char)
    assert aligned == text + expected_fill


def test_align_left() -> None:
    text = 'foo'
    fill_char = '-'
    width = 5
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char + fill_char


def test_align_left_multiline() -> None:
    # Without style
    text = "foo\nshoes"
    fill_char = '-'
    width = 7
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == 'foo----\nshoes--'

    # With style
    reset_all = str(ansi.TextStyle.RESET_ALL)
    blue = str(ansi.Fg.BLUE)
    red = str(ansi.Fg.RED)
    green = str(ansi.Fg.GREEN)
    fg_reset = str(ansi.Fg.RESET)

    text = f"{blue}foo{red}moo\nshoes{fg_reset}"
    fill_char = f"{green}-{fg_reset}"
    width = 7
    aligned = cu.align_left(text, fill_char=fill_char, width=width)

    expected = f"{reset_all}{blue}foo{red}moo{reset_all}{green}-{fg_reset}{reset_all}\n"
    expected += f"{reset_all}{red}shoes{fg_reset}{reset_all}{green}--{fg_reset}{reset_all}"
    assert aligned == expected


def test_align_left_wide_text() -> None:
    text = '苹'
    fill_char = '-'
    width = 4
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char + fill_char


def test_align_left_wide_fill() -> None:
    text = 'foo'
    fill_char = '苹'
    width = 5
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char


def test_align_left_wide_fill_needs_padding() -> None:
    """Test when fill_char's display width does not divide evenly into gap"""
    text = 'foo'
    fill_char = '苹'
    width = 6
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char + ' '


def test_align_center() -> None:
    text = 'foo'
    fill_char = '-'
    width = 5
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char


def test_align_center_multiline() -> None:
    # Without style
    text = "foo\nshoes"
    fill_char = '-'
    width = 7
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == '--foo--\n-shoes-'

    # With style
    reset_all = str(ansi.TextStyle.RESET_ALL)
    blue = str(ansi.Fg.BLUE)
    red = str(ansi.Fg.RED)
    green = str(ansi.Fg.GREEN)
    fg_reset = str(ansi.Fg.RESET)

    text = f"{blue}foo{red}moo\nshoes{fg_reset}"
    fill_char = f"{green}-{fg_reset}"
    width = 10
    aligned = cu.align_center(text, fill_char=fill_char, width=width)

    expected = f"{reset_all}{green}--{fg_reset}{reset_all}{blue}foo{red}moo{reset_all}{green}--{fg_reset}{reset_all}\n"
    expected += f"{reset_all}{green}--{fg_reset}{reset_all}{red}shoes{fg_reset}{reset_all}{green}---{fg_reset}{reset_all}"
    assert aligned == expected


def test_align_center_wide_text() -> None:
    text = '苹'
    fill_char = '-'
    width = 4
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char


def test_align_center_wide_fill() -> None:
    text = 'foo'
    fill_char = '苹'
    width = 7
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char


def test_align_center_wide_fill_needs_right_padding() -> None:
    """Test when fill_char's display width does not divide evenly into right gap"""
    text = 'foo'
    fill_char = '苹'
    width = 8
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char + ' '


def test_align_center_wide_fill_needs_left_and_right_padding() -> None:
    """Test when fill_char's display width does not divide evenly into either gap"""
    text = 'foo'
    fill_char = '苹'
    width = 9
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + ' ' + text + fill_char + ' '


def test_align_right() -> None:
    text = 'foo'
    fill_char = '-'
    width = 5
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + fill_char + text


def test_align_right_multiline() -> None:
    # Without style
    text = "foo\nshoes"
    fill_char = '-'
    width = 7
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == '----foo\n--shoes'

    # With style
    reset_all = str(ansi.TextStyle.RESET_ALL)
    blue = str(ansi.Fg.BLUE)
    red = str(ansi.Fg.RED)
    green = str(ansi.Fg.GREEN)
    fg_reset = str(ansi.Fg.RESET)

    text = f"{blue}foo{red}moo\nshoes{fg_reset}"
    fill_char = f"{green}-{fg_reset}"
    width = 7
    aligned = cu.align_right(text, fill_char=fill_char, width=width)

    expected = f"{reset_all}{green}-{fg_reset}{reset_all}{blue}foo{red}moo{reset_all}\n"
    expected += f"{reset_all}{green}--{fg_reset}{reset_all}{red}shoes{fg_reset}{reset_all}"
    assert aligned == expected


def test_align_right_wide_text() -> None:
    text = '苹'
    fill_char = '-'
    width = 4
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + fill_char + text


def test_align_right_wide_fill() -> None:
    text = 'foo'
    fill_char = '苹'
    width = 5
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text


def test_align_right_wide_fill_needs_padding() -> None:
    """Test when fill_char's display width does not divide evenly into gap"""
    text = 'foo'
    fill_char = '苹'
    width = 6
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + ' ' + text


def test_to_bool_str_true() -> None:
    assert cu.to_bool('true')
    assert cu.to_bool('True')
    assert cu.to_bool('TRUE')
    assert cu.to_bool('tRuE')


def test_to_bool_str_false() -> None:
    assert not cu.to_bool('false')
    assert not cu.to_bool('False')
    assert not cu.to_bool('FALSE')
    assert not cu.to_bool('fAlSe')


def test_to_bool_str_invalid() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        cu.to_bool('other')


def test_to_bool_bool() -> None:
    assert cu.to_bool(True)
    assert not cu.to_bool(False)


def test_to_bool_int() -> None:
    assert cu.to_bool(1)
    assert cu.to_bool(-1)
    assert not cu.to_bool(0)


def test_to_bool_float() -> None:
    assert cu.to_bool(2.35)
    assert cu.to_bool(0.25)
    assert cu.to_bool(-3.1415)
    assert not cu.to_bool(0)


def test_find_editor_specified() -> None:
    expected_editor = os.path.join('fake_dir', 'editor')
    with mock.patch.dict(os.environ, {'EDITOR': expected_editor}):
        editor = cu.find_editor()
    assert editor == expected_editor


def test_find_editor_not_specified() -> None:
    # Use existing path env setting. Something in the editor list should be found.
    editor = cu.find_editor()
    assert editor

    # Overwrite path env setting with invalid path, clear all other env vars so no editor should be found.
    with mock.patch.dict(os.environ, {'PATH': 'fake_dir'}, clear=True):
        editor = cu.find_editor()
    assert editor is None


def test_similarity() -> None:
    suggested_command = cu.suggest_similar("comand", ["command", "UNRELATED", "NOT_SIMILAR"])
    assert suggested_command == "command"
    suggested_command = cu.suggest_similar("command", ["COMMAND", "acommands"])
    assert suggested_command == "COMMAND"


def test_similarity_without_good_canididates() -> None:
    suggested_command = cu.suggest_similar("comand", ["UNRELATED", "NOT_SIMILAR"])
    assert suggested_command is None
    suggested_command = cu.suggest_similar("comand", [])
    assert suggested_command is None


def test_similarity_overwrite_function() -> None:
    options = ["history", "test"]
    suggested_command = cu.suggest_similar("test", options)
    assert suggested_command == 'test'

    def custom_similarity_function(s1, s2) -> float:
        return 1.0 if 'history' in (s1, s2) else 0.0

    suggested_command = cu.suggest_similar("test", options, similarity_function_to_use=custom_similarity_function)
    assert suggested_command == 'history'

    suggested_command = cu.suggest_similar("history", options, similarity_function_to_use=custom_similarity_function)
    assert suggested_command == 'history'

    suggested_command = cu.suggest_similar("test", ["test"], similarity_function_to_use=custom_similarity_function)
    assert suggested_command is None


def test_get_types_invalid_input() -> None:
    x = 1
    with pytest.raises(ValueError, match="Argument passed to get_types should be a function or method"):
        cu.get_types(x)


def test_get_types_empty() -> None:
    def a(b):
        print(b)

    param_ann, ret_ann = cu.get_types(a)
    assert ret_ann is None
    assert param_ann == {}


def test_get_types_non_empty() -> None:
    def foo(x: int) -> str:
        return f"{x * x}"

    param_ann, ret_ann = cu.get_types(foo)
    assert ret_ann is str
    param_name, param_value = next(iter(param_ann.items()))
    assert param_name == 'x'
    assert param_value is int


def test_get_types_method() -> None:
    class Foo:
        def bar(self, x: bool) -> None:
            print(x)

    f = Foo()

    param_ann, ret_ann = cu.get_types(f.bar)
    assert ret_ann is None
    assert len(param_ann) == 1
    param_name, param_value = next(iter(param_ann.items()))
    assert param_name == 'x'
    assert param_value is bool
