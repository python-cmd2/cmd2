# coding=utf-8
# flake8: noqa E302
"""
Unit testing for cmd2/utils.py module.
"""
import signal
import sys
import time

import pytest

import cmd2.utils as cu
from cmd2.constants import HORIZONTAL_ELLIPSIS

HELLO_WORLD = 'Hello, world!'


def test_strip_quotes_no_quotes():
    base_str = HELLO_WORLD
    stripped = cu.strip_quotes(base_str)
    assert base_str == stripped

def test_strip_quotes_with_quotes():
    base_str = '"' + HELLO_WORLD + '"'
    stripped = cu.strip_quotes(base_str)
    assert stripped == HELLO_WORLD

def test_remove_duplicates_no_duplicates():
    no_dups = [5, 4, 3, 2, 1]
    assert cu.remove_duplicates(no_dups) == no_dups

def test_remove_duplicates_with_duplicates():
    duplicates = [1, 1, 2, 3, 9, 9, 7, 8]
    assert cu.remove_duplicates(duplicates) == [1, 2, 3, 9, 7, 8]

def test_unicode_normalization():
    s1 = 'café'
    s2 = 'cafe\u0301'
    assert s1 != s2
    assert cu.norm_fold(s1) == cu.norm_fold(s2)

def test_unicode_casefold():
    micro = 'µ'
    micro_cf = micro.casefold()
    assert micro != micro_cf
    assert cu.norm_fold(micro) == cu.norm_fold(micro_cf)

def test_alphabetical_sort():
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'cafeteria']
    assert cu.alphabetical_sort(my_list) == ['A', 'cafeteria', 'café', 'micro', 'unity', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.alphabetical_sort(my_list) == ['a1', 'A11', 'A2', 'a22', 'a3']

def test_try_int_or_force_to_lower_case():
    str1 = '17'
    assert cu.try_int_or_force_to_lower_case(str1) == 17
    str1 = 'ABC'
    assert cu.try_int_or_force_to_lower_case(str1) == 'abc'
    str1 = 'X19'
    assert cu.try_int_or_force_to_lower_case(str1) == 'x19'
    str1 = ''
    assert cu.try_int_or_force_to_lower_case(str1) == ''

def test_natural_keys():
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    my_list.sort(key=cu.natural_keys)
    assert my_list == ['a1', 'A2', 'a3', 'A11', 'a22']

def test_natural_sort():
    my_list = ['café', 'µ', 'A', 'micro', 'unity', 'x1', 'X2', 'X11', 'X0', 'x22']
    assert cu.natural_sort(my_list) == ['A', 'café', 'micro', 'unity', 'X0', 'x1', 'X2', 'X11', 'x22', 'µ']
    my_list = ['a3', 'a22', 'A2', 'A11', 'a1']
    assert cu.natural_sort(my_list) == ['a1', 'A2', 'a3', 'A11', 'a22']

def test_is_quoted_short():
    my_str = ''
    assert not cu.is_quoted(my_str)
    your_str = '"'
    assert not cu.is_quoted(your_str)

def test_is_quoted_yes():
    my_str = '"This is a test"'
    assert cu.is_quoted(my_str)
    your_str = "'of the emergengy broadcast system'"
    assert cu.is_quoted(your_str)

def test_is_quoted_no():
    my_str = '"This is a test'
    assert not cu.is_quoted(my_str)
    your_str = "of the emergengy broadcast system'"
    assert not cu.is_quoted(your_str)
    simple_str = "hello world"
    assert not cu.is_quoted(simple_str)

def test_quote_string():
    my_str = "Hello World"
    assert cu.quote_string(my_str) == '"' + my_str + '"'

    my_str = "'Hello World'"
    assert cu.quote_string(my_str) == '"' + my_str + '"'

    my_str = '"Hello World"'
    assert cu.quote_string(my_str) == "'" + my_str + "'"

def test_quote_string_if_needed_yes():
    my_str = "Hello World"
    assert cu.quote_string_if_needed(my_str) == '"' + my_str + '"'
    your_str = '"foo" bar'
    assert cu.quote_string_if_needed(your_str) == "'" + your_str + "'"

def test_quote_string_if_needed_no():
    my_str = "HelloWorld"
    assert cu.quote_string_if_needed(my_str) == my_str
    your_str = "'Hello World'"
    assert cu.quote_string_if_needed(your_str) == your_str


@pytest.fixture
def stdout_sim():
    stdsim = cu.StdSim(sys.stdout, echo=True)
    return stdsim


def test_stdsim_write_str(stdout_sim):
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str

def test_stdsim_write_bytes(stdout_sim):
    b_str = b'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.write(b_str)

def test_stdsim_buffer_write_bytes(stdout_sim):
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    assert stdout_sim.getvalue() == b_str.decode()
    assert stdout_sim.getbytes() == b_str

def test_stdsim_buffer_write_str(stdout_sim):
    my_str = 'Hello World'
    with pytest.raises(TypeError):
        stdout_sim.buffer.write(my_str)

def test_stdsim_read(stdout_sim):
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    # getvalue() returns the value and leaves it unaffected internally
    assert stdout_sim.getvalue() == my_str
    # read() returns the value and then clears the internal buffer
    assert stdout_sim.read() == my_str
    assert stdout_sim.getvalue() == ''

def test_stdsim_read_bytes(stdout_sim):
    b_str = b'Hello World'
    stdout_sim.buffer.write(b_str)
    # getbytes() returns the value and leaves it unaffected internally
    assert stdout_sim.getbytes() == b_str
    # read_bytes() returns the value and then clears the internal buffer
    assert stdout_sim.readbytes() == b_str
    assert stdout_sim.getbytes() == b''

def test_stdsim_clear(stdout_sim):
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    assert stdout_sim.getvalue() == my_str
    stdout_sim.clear()
    assert stdout_sim.getvalue() == ''

def test_stdsim_getattr_exist(stdout_sim):
    # Here the StdSim getattr is allowing us to access methods within StdSim
    my_str = 'Hello World'
    stdout_sim.write(my_str)
    val_func = getattr(stdout_sim, 'getvalue')
    assert val_func() == my_str

def test_stdsim_getattr_noexist(stdout_sim):
    # Here the StdSim getattr is allowing us to access methods defined by the inner stream
    assert not stdout_sim.isatty()

def test_stdsim_pause_storage(stdout_sim):
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

def test_stdsim_line_buffering(base_app):
    # This exercises the case of writing binary data that contains new lines/carriage returns to a StdSim
    # when line buffering is on. The output should immediately be flushed to the underlying stream.
    import os
    import tempfile
    file = tempfile.NamedTemporaryFile(mode='wt')
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
    kwargs = dict()
    if sys.platform.startswith('win'):
        command = 'timeout -t 5 /nobreak'
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        command = 'sleep 5'
        kwargs['start_new_session'] = True

    proc = subprocess.Popen(command, shell=True, **kwargs)
    pr = cu.ProcReader(proc, None, None)
    return pr

def test_proc_reader_send_sigint(pr_none):
    assert pr_none._proc.poll() is None
    pr_none.send_sigint()

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
        assert ret_code == -signal.SIGINT

def test_proc_reader_terminate(pr_none):
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

def test_context_flag_bool(context_flag):
    assert not context_flag
    with context_flag:
        assert context_flag

def test_context_flag_exit_err(context_flag):
    with pytest.raises(ValueError):
        context_flag.__exit__()


def test_truncate_line():
    line = 'long'
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == 'lo' + HORIZONTAL_ELLIPSIS

def test_truncate_line_already_fits():
    line = 'long'
    max_width = 4
    truncated = cu.truncate_line(line, max_width)
    assert truncated == line

def test_truncate_line_with_newline():
    line = 'fo\no'
    max_width = 2
    with pytest.raises(ValueError):
        cu.truncate_line(line, max_width)

def test_truncate_line_width_is_too_small():
    line = 'foo'
    max_width = 0
    with pytest.raises(ValueError):
        cu.truncate_line(line, max_width)

def test_truncate_line_wide_text():
    line = '苹苹other'
    max_width = 6
    truncated = cu.truncate_line(line, max_width)
    assert truncated == '苹苹o' + HORIZONTAL_ELLIPSIS

def test_truncate_line_split_wide_text():
    """Test when truncation results in a string which is shorter than max_width"""
    line = '1苹2苹'
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == '1' + HORIZONTAL_ELLIPSIS

def test_truncate_line_tabs():
    line = 'has\ttab'
    max_width = 9
    truncated = cu.truncate_line(line, max_width)
    assert truncated == 'has    t' + HORIZONTAL_ELLIPSIS

def test_truncate_with_style():
    from cmd2 import ansi

    before_style = ansi.fg.blue + ansi.UNDERLINE_ENABLE
    after_style = ansi.fg.reset + ansi.UNDERLINE_DISABLE

    # Style only before truncated text
    line = before_style + 'long'
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == before_style + 'lo' + HORIZONTAL_ELLIPSIS

    # Style before and after truncated text
    line = before_style + 'long' + after_style
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == before_style + 'lo' + HORIZONTAL_ELLIPSIS + after_style

    # Style only after truncated text
    line = 'long' + after_style
    max_width = 3
    truncated = cu.truncate_line(line, max_width)
    assert truncated == 'lo' + HORIZONTAL_ELLIPSIS + after_style

def test_align_text_fill_char_is_tab():
    text = 'foo'
    fill_char = '\t'
    width = 5
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)
    assert aligned == text + '  '

def test_align_text_with_style():
    from cmd2 import ansi

    # Single line with only left fill
    text = ansi.style('line1', fg=ansi.fg.bright_blue)
    fill_char = ansi.style('-', fg=ansi.fg.bright_yellow)
    width = 6

    aligned = cu.align_text(text, cu.TextAlignment.RIGHT, fill_char=fill_char, width=width)

    left_fill = ansi.RESET_ALL + fill_char + ansi.RESET_ALL
    right_fill = ansi.RESET_ALL
    line_1_text = ansi.fg.bright_blue + 'line1' + ansi.FG_RESET

    assert aligned == (left_fill + line_1_text + right_fill)

    # Single line with only right fill
    text = ansi.style('line1', fg=ansi.fg.bright_blue)
    fill_char = ansi.style('-', fg=ansi.fg.bright_yellow)
    width = 6

    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)

    left_fill = ansi.RESET_ALL
    right_fill = ansi.RESET_ALL + fill_char + ansi.RESET_ALL
    line_1_text = ansi.fg.bright_blue + 'line1' + ansi.FG_RESET

    assert aligned == (left_fill + line_1_text + right_fill)

    # Multiple lines to show that style is preserved across all lines. Also has left and right fill.
    text = ansi.style('line1\nline2', fg=ansi.fg.bright_blue)
    fill_char = ansi.style('-', fg=ansi.fg.bright_yellow)
    width = 7

    aligned = cu.align_text(text, cu.TextAlignment.CENTER, fill_char=fill_char, width=width)

    left_fill = ansi.RESET_ALL + fill_char + ansi.RESET_ALL
    right_fill = ansi.RESET_ALL + fill_char + ansi.RESET_ALL
    line_1_text = ansi.fg.bright_blue + 'line1'
    line_2_text = ansi.fg.bright_blue + 'line2' + ansi.FG_RESET

    assert aligned == (left_fill + line_1_text + right_fill + '\n' +
                       left_fill + line_2_text + right_fill)

def test_align_text_width_is_too_small():
    text = 'foo'
    fill_char = '-'
    width = 0
    with pytest.raises(ValueError):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)

def test_align_text_fill_char_is_too_long():
    text = 'foo'
    fill_char = 'fill'
    width = 5
    with pytest.raises(TypeError):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)

def test_align_text_fill_char_is_newline():
    text = 'foo'
    fill_char = '\n'
    width = 5
    with pytest.raises(ValueError):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)

def test_align_text_has_tabs():
    text = '\t\tfoo'
    fill_char = '-'
    width = 10
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width, tab_width=2)
    assert aligned == '    ' + 'foo' + '---'

def test_align_text_blank():
    text = ''
    fill_char = '-'
    width = 5
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)
    assert aligned == fill_char * width

def test_align_text_wider_than_width():
    text = 'long text field'
    fill_char = '-'
    width = 8
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)
    assert aligned == text

def test_align_text_wider_than_width_truncate():
    text = 'long text field'
    fill_char = '-'
    width = 8
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width, truncate=True)
    assert aligned == 'long te' + HORIZONTAL_ELLIPSIS

def test_align_text_wider_than_width_truncate_add_fill():
    """Test when truncation results in a string which is shorter than width and align_text adds filler"""
    text = '1苹2苹'
    fill_char = '-'
    width = 3
    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width, truncate=True)
    assert aligned == '1' + HORIZONTAL_ELLIPSIS + fill_char

def test_align_text_has_unprintable():
    text = 'foo\x02'
    fill_char = '-'
    width = 5
    with pytest.raises(ValueError):
        cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char, width=width)

def test_align_text_term_width():
    import shutil
    from cmd2 import ansi
    text = 'foo'
    fill_char = ' '

    term_width = shutil.get_terminal_size().columns
    expected_fill = (term_width - ansi.style_aware_wcswidth(text)) * fill_char

    aligned = cu.align_text(text, cu.TextAlignment.LEFT, fill_char=fill_char)
    assert aligned == text + expected_fill

def test_align_left():
    text = 'foo'
    fill_char = '-'
    width = 5
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char + fill_char

def test_align_left_multiline():
    text = "foo\nshoes"
    fill_char = '-'
    width = 7
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == ('foo----\n'
                       'shoes--')

def test_align_left_wide_text():
    text = '苹'
    fill_char = '-'
    width = 4
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char + fill_char

def test_align_left_wide_fill():
    text = 'foo'
    fill_char = '苹'
    width = 5
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char

def test_align_left_wide_fill_needs_padding():
    """Test when fill_char's display width does not divide evenly into gap"""
    text = 'foo'
    fill_char = '苹'
    width = 6
    aligned = cu.align_left(text, fill_char=fill_char, width=width)
    assert aligned == text + fill_char + ' '

def test_align_center():
    text = 'foo'
    fill_char = '-'
    width = 5
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char

def test_align_center_multiline():
    text = "foo\nshoes"
    fill_char = '-'
    width = 7
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == ('--foo--\n'
                       '-shoes-')

def test_align_center_wide_text():
    text = '苹'
    fill_char = '-'
    width = 4
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char

def test_align_center_wide_fill():
    text = 'foo'
    fill_char = '苹'
    width = 7
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char

def test_align_center_wide_fill_needs_right_padding():
    """Test when fill_char's display width does not divide evenly into right gap"""
    text = 'foo'
    fill_char = '苹'
    width = 8
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text + fill_char + ' '

def test_align_center_wide_fill_needs_left_and_right_padding():
    """Test when fill_char's display width does not divide evenly into either gap"""
    text = 'foo'
    fill_char = '苹'
    width = 9
    aligned = cu.align_center(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + ' ' + text + fill_char + ' '

def test_align_right():
    text = 'foo'
    fill_char = '-'
    width = 5
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + fill_char + text

def test_align_right_multiline():
    text = "foo\nshoes"
    fill_char = '-'
    width = 7
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == ('----foo\n'
                       '--shoes')

def test_align_right_wide_text():
    text = '苹'
    fill_char = '-'
    width = 4
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + fill_char + text

def test_align_right_wide_fill():
    text = 'foo'
    fill_char = '苹'
    width = 5
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + text

def test_align_right_wide_fill_needs_padding():
    """Test when fill_char's display width does not divide evenly into gap"""
    text = 'foo'
    fill_char = '苹'
    width = 6
    aligned = cu.align_right(text, fill_char=fill_char, width=width)
    assert aligned == fill_char + ' ' + text


def test_str_to_bool_true():
    assert cu.str_to_bool('true')
    assert cu.str_to_bool('True')
    assert cu.str_to_bool('TRUE')
    assert cu.str_to_bool('tRuE')

def test_str_to_bool_false():
    assert not cu.str_to_bool('false')
    assert not cu.str_to_bool('False')
    assert not cu.str_to_bool('FALSE')
    assert not cu.str_to_bool('fAlSe')

def test_str_to_bool_invalid():
    with pytest.raises(ValueError):
        cu.str_to_bool('other')

def test_str_to_bool_bad_input():
    with pytest.raises(ValueError):
        cu.str_to_bool(1)
