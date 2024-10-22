# coding=utf-8
# flake8: noqa E501
"""
Unit testing for cmd2/table_creator.py module
"""

import pytest

from cmd2 import (
    Bg,
    Fg,
    TextStyle,
    ansi,
)
from cmd2.table_creator import (
    AlternatingTable,
    BorderedTable,
    Column,
    HorizontalAlignment,
    SimpleTable,
    TableCreator,
    VerticalAlignment,
)

# Turn off black formatting for entire file so multiline strings
# can be visually aligned to match the tables being tested.
# fmt: off


def test_column_creation():
    # Width less than 1
    with pytest.raises(ValueError) as excinfo:
        Column("Column 1", width=0)
    assert "Column width cannot be less than 1" in str(excinfo.value)

    # Width specified
    c = Column("header", width=20)
    assert c.width == 20

    # max_data_lines less than 1
    with pytest.raises(ValueError) as excinfo:
        Column("Column 1", max_data_lines=0)
    assert "Max data lines cannot be less than 1" in str(excinfo.value)

    # No width specified, blank label
    c = Column("")
    assert c.width < 0
    tc = TableCreator([c])
    assert tc.cols[0].width == 1

    # No width specified, label isn't blank but has no width
    c = Column(ansi.style('', fg=Fg.GREEN))
    assert c.width < 0
    tc = TableCreator([c])
    assert tc.cols[0].width == 1

    # No width specified, label has width
    c = Column("a line")
    assert c.width < 0
    tc = TableCreator([c])
    assert tc.cols[0].width == ansi.style_aware_wcswidth("a line")

    # No width specified, label has width and multiple lines
    c = Column("short\nreally long")
    assert c.width < 0
    tc = TableCreator([c])
    assert tc.cols[0].width == ansi.style_aware_wcswidth("really long")

    # No width specified, label has tabs
    c = Column("line\twith\ttabs")
    assert c.width < 0
    tc = TableCreator([c])
    assert tc.cols[0].width == ansi.style_aware_wcswidth("line    with    tabs")

    # Add basic tests for style_header_text and style_data_text to make sure these members don't get removed.
    c = Column("Column 1")
    assert c.style_header_text is True
    assert c.style_data_text is True

    c = Column("Column 1", style_header_text=False)
    assert c.style_header_text is False
    assert c.style_data_text is True

    c = Column("Column 1", style_data_text=False)
    assert c.style_header_text is True
    assert c.style_data_text is False


def test_column_alignment():
    column_1 = Column(
        "Col 1",
        width=10,
        header_horiz_align=HorizontalAlignment.LEFT,
        header_vert_align=VerticalAlignment.TOP,
        data_horiz_align=HorizontalAlignment.RIGHT,
        data_vert_align=VerticalAlignment.BOTTOM,
    )
    column_2 = Column(
        "Col 2",
        width=10,
        header_horiz_align=HorizontalAlignment.RIGHT,
        header_vert_align=VerticalAlignment.BOTTOM,
        data_horiz_align=HorizontalAlignment.CENTER,
        data_vert_align=VerticalAlignment.MIDDLE,
    )
    column_3 = Column(
        "Col 3",
        width=10,
        header_horiz_align=HorizontalAlignment.CENTER,
        header_vert_align=VerticalAlignment.MIDDLE,
        data_horiz_align=HorizontalAlignment.LEFT,
        data_vert_align=VerticalAlignment.TOP,
    )
    column_4 = Column("Three\nline\nheader", width=10)

    columns = [column_1, column_2, column_3, column_4]
    tc = TableCreator(columns)

    # Check defaults
    assert column_4.header_horiz_align == HorizontalAlignment.LEFT
    assert column_4.header_vert_align == VerticalAlignment.BOTTOM
    assert column_4.data_horiz_align == HorizontalAlignment.LEFT
    assert column_4.data_vert_align == VerticalAlignment.TOP

    # Create a header row
    row_data = [col.header for col in columns]
    header = tc.generate_row(row_data=row_data, is_header=True)
    assert header == (
        'Col 1                               Three     \n'
        '                          Col 3     line      \n'
        '                 Col 2              header    '
    )

    # Create a data row
    row_data = ["Val 1", "Val 2", "Val 3", "Three\nline\ndata"]
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == (
        '                        Val 3       Three     \n'
        '              Val 2                 line      \n'
        '     Val 1                          data      '
    )


def test_blank_last_line():
    """This tests that an empty line is inserted when the last data line is blank"""
    column_1 = Column("Col 1", width=10)
    tc = TableCreator([column_1])

    row_data = ['my line\n\n']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('my line   \n'
                   '          ')

    row_data = ['\n']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == '          '

    row_data = ['']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == '          '


def test_wrap_text():
    column_1 = Column("Col 1", width=10)
    tc = TableCreator([column_1])

    # Test normal wrapping
    row_data = ['Some text to wrap\nA new line that will wrap\nNot wrap\n 1  2   3']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('Some text \n'
                   'to wrap   \n'
                   'A new line\n'
                   'that will \n'
                   'wrap      \n'
                   'Not wrap  \n'
                   ' 1  2   3 ')

    # Test preserving a multiple space sequence across a line break
    row_data = ['First      last one']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('First     \n'
                   ' last one ')


def test_wrap_text_max_lines():
    column_1 = Column("Col 1", width=10, max_data_lines=2)
    tc = TableCreator([column_1])

    # Test not needing to truncate the final line
    row_data = ['First line last line']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('First line\n'
                   'last line ')

    # Test having to truncate the last word because it's too long for the final line
    row_data = ['First line last lineextratext']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('First line\n'
                   'last line…')

    # Test having to truncate the last word because it fits the final line but there is more text not being included
    row_data = ['First line thistxtfit extra']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('First line\n'
                   'thistxtfi…')

    # Test having to truncate the last word because it fits the final line but there are more lines not being included
    row_data = ['First line thistxtfit\nextra']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('First line\n'
                   'thistxtfi…')

    # Test having space left on the final line and adding an ellipsis because there are more lines not being included
    row_data = ['First line last line\nextra line']
    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('First line\n'
                   'last line…')


def test_wrap_long_word():
    # Make sure words wider than column start on own line and wrap
    column_1 = Column("LongColumnName", width=10)
    column_2 = Column("Col 2", width=10)

    columns = [column_1, column_2]
    tc = TableCreator(columns)

    # Test header row
    row_data = [col.header for col in columns]
    header = tc.generate_row(row_data, is_header=True)
    assert header == ('LongColumn            \n'
                      'Name        Col 2     ')

    # Test data row
    row_data = list()

    # Long word should start on the first line (style should not affect width)
    row_data.append(ansi.style("LongerThan10", fg=Fg.GREEN))

    # Long word should start on the second line
    row_data.append("Word LongerThan10")

    row = tc.generate_row(row_data=row_data, is_header=False)
    expected = (
            TextStyle.RESET_ALL
            + Fg.GREEN
            + "LongerThan"
            + TextStyle.RESET_ALL
            + "  Word      \n"
            + TextStyle.RESET_ALL
            + Fg.GREEN
            + "10"
            + Fg.RESET
            + TextStyle.RESET_ALL
            + '        '
            + TextStyle.RESET_ALL
            + '  LongerThan\n'
              '            10        '
    )
    assert row == expected


def test_wrap_long_word_max_data_lines():
    column_1 = Column("Col 1", width=10, max_data_lines=2)
    column_2 = Column("Col 2", width=10, max_data_lines=2)
    column_3 = Column("Col 3", width=10, max_data_lines=2)
    column_4 = Column("Col 4", width=10, max_data_lines=1)

    columns = [column_1, column_2, column_3, column_4]
    tc = TableCreator(columns)

    row_data = list()

    # This long word will exactly fit the last line and it's the final word in the text. No ellipsis should appear.
    row_data.append("LongerThan10FitsLast")

    # This long word will exactly fit the last line but it's not the final word in the text.
    # Make sure ellipsis word's final character.
    row_data.append("LongerThan10FitsLast\nMore lines")

    # This long word will run over the last line. Make sure it is truncated.
    row_data.append("LongerThan10RunsOverLast")

    # This long word will start on the final line after another word. Therefore it won't wrap but will instead be truncated.
    row_data.append("A LongerThan10RunsOverLast")

    row = tc.generate_row(row_data=row_data, is_header=False)
    assert row == ('LongerThan  LongerThan  LongerThan  A LongerT…\n'
                   '10FitsLast  10FitsLas…  10RunsOve…            ')


def test_wrap_long_char_wider_than_max_width():
    """
    This tests case where a character is wider than max_width. This can happen if max_width
    is 1 and the text contains wide characters (e.g. East Asian). Replace it with an ellipsis.
    """
    column_1 = Column("Col 1", width=1)
    tc = TableCreator([column_1])
    row = tc.generate_row(row_data=['深'], is_header=False)
    assert row == '…'


def test_generate_row_exceptions():
    column_1 = Column("Col 1")
    tc = TableCreator([column_1])
    row_data = ['fake']

    # fill_char too long
    with pytest.raises(TypeError) as excinfo:
        tc.generate_row(row_data=row_data, is_header=False, fill_char='too long')
    assert "Fill character must be exactly one character long" in str(excinfo.value)

    # Unprintable characters
    for arg in ['fill_char', 'pre_line', 'inter_cell', 'post_line']:
        kwargs = {arg: '\n'}
        with pytest.raises(ValueError) as excinfo:
            tc.generate_row(row_data=row_data, is_header=False, **kwargs)
        assert "{} contains an unprintable character".format(arg) in str(excinfo.value)

    # Data with too many columns
    row_data = ['Data 1', 'Extra Column']
    with pytest.raises(ValueError) as excinfo:
        tc.generate_row(row_data=row_data, is_header=False)
    assert "Length of row_data must match length of cols" in str(excinfo.value)


def test_tabs():
    column_1 = Column("Col\t1", width=20)
    column_2 = Column("Col 2")
    columns = [column_1, column_2]
    tc = TableCreator(columns, tab_width=2)

    row_data = [col.header for col in columns]
    row = tc.generate_row(row_data, is_header=True, fill_char='\t', pre_line='\t', inter_cell='\t', post_line='\t')
    assert row == '  Col  1                Col 2  '

    with pytest.raises(ValueError) as excinfo:
        TableCreator([column_1, column_2], tab_width=0)
    assert "Tab width cannot be less than 1" in str(excinfo.value)


def test_simple_table_creation():
    column_1 = Column("Col 1", width=16)
    column_2 = Column("Col 2", width=16)

    row_data = list()
    row_data.append(["Col 1 Row 1", "Col 2 Row 1"])
    row_data.append(["Col 1 Row 2", "Col 2 Row 2"])

    # Default options
    st = SimpleTable([column_1, column_2])
    table = st.generate_table(row_data)

    assert table == (
        'Col 1             Col 2           \n'
        '----------------------------------\n'
        'Col 1 Row 1       Col 2 Row 1     \n'
        '                                  \n'
        'Col 1 Row 2       Col 2 Row 2     '
    )

    # Custom column spacing
    st = SimpleTable([column_1, column_2], column_spacing=5)
    table = st.generate_table(row_data)

    assert table == (
        'Col 1                Col 2           \n'
        '-------------------------------------\n'
        'Col 1 Row 1          Col 2 Row 1     \n'
        '                                     \n'
        'Col 1 Row 2          Col 2 Row 2     '
    )

    # Custom divider
    st = SimpleTable([column_1, column_2], divider_char='─')
    table = st.generate_table(row_data)

    assert table == (
        'Col 1             Col 2           \n'
        '──────────────────────────────────\n'
        'Col 1 Row 1       Col 2 Row 1     \n'
        '                                  \n'
        'Col 1 Row 2       Col 2 Row 2     '
    )

    # No divider
    st = SimpleTable([column_1, column_2], divider_char=None)
    no_divider_1 = st.generate_table(row_data)

    st = SimpleTable([column_1, column_2], divider_char='')
    no_divider_2 = st.generate_table(row_data)

    assert no_divider_1 == no_divider_2 == (
        'Col 1             Col 2           \n'
        'Col 1 Row 1       Col 2 Row 1     \n'
        '                                  \n'
        'Col 1 Row 2       Col 2 Row 2     '
    )

    # No row spacing
    st = SimpleTable([column_1, column_2])
    table = st.generate_table(row_data, row_spacing=0)
    assert table == (
        'Col 1             Col 2           \n'
        '----------------------------------\n'
        'Col 1 Row 1       Col 2 Row 1     \n'
        'Col 1 Row 2       Col 2 Row 2     '
    )

    # No header
    st = SimpleTable([column_1, column_2])
    table = st.generate_table(row_data, include_header=False)

    assert table == ('Col 1 Row 1       Col 2 Row 1     \n'
                     '                                  \n'
                     'Col 1 Row 2       Col 2 Row 2     ')

    # Wide custom divider (divider needs no padding)
    st = SimpleTable([column_1, column_2], divider_char='深')
    table = st.generate_table(row_data)

    assert table == (
        'Col 1             Col 2           \n'
        '深深深深深深深深深深深深深深深深深\n'
        'Col 1 Row 1       Col 2 Row 1     \n'
        '                                  \n'
        'Col 1 Row 2       Col 2 Row 2     '
    )

    # Wide custom divider (divider needs padding)
    st = SimpleTable([column_1, Column("Col 2", width=17)],
                     divider_char='深')
    table = st.generate_table(row_data)

    assert table == (
        'Col 1             Col 2            \n'
        '深深深深深深深深深深深深深深深深深 \n'
        'Col 1 Row 1       Col 2 Row 1      \n'
        '                                   \n'
        'Col 1 Row 2       Col 2 Row 2      '
    )

    # Invalid column spacing
    with pytest.raises(ValueError) as excinfo:
        SimpleTable([column_1, column_2], column_spacing=-1)
    assert "Column spacing cannot be less than 0" in str(excinfo.value)

    # Invalid divider character
    with pytest.raises(TypeError) as excinfo:
        SimpleTable([column_1, column_2], divider_char='too long')
    assert "Divider character must be exactly one character long" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        SimpleTable([column_1, column_2], divider_char='\n')
    assert "Divider character is an unprintable character" in str(excinfo.value)

    # Invalid row spacing
    st = SimpleTable([column_1, column_2])
    with pytest.raises(ValueError) as excinfo:
        st.generate_table(row_data, row_spacing=-1)
    assert "Row spacing cannot be less than 0" in str(excinfo.value)

    # Test header and data colors
    st = SimpleTable([column_1, column_2], divider_char=None, header_bg=Bg.GREEN, data_bg=Bg.LIGHT_BLUE)
    table = st.generate_table(row_data)
    assert table == (
        '\x1b[0m\x1b[42mCol 1\x1b[49m\x1b[0m\x1b[42m           \x1b[49m\x1b[0m\x1b[42m  \x1b[49m\x1b[0m\x1b[42mCol 2\x1b[49m\x1b[0m\x1b[42m           \x1b[49m\x1b[0m\n'
        '\x1b[0m\x1b[104mCol 1 Row 1\x1b[49m\x1b[0m\x1b[104m     \x1b[49m\x1b[0m\x1b[104m  \x1b[49m\x1b[0m\x1b[104mCol 2 Row 1\x1b[49m\x1b[0m\x1b[104m     \x1b[49m\x1b[0m\n'
        '\x1b[0m\x1b[0m\x1b[104m                                  \x1b[49m\x1b[0m\n'
        '\x1b[0m\x1b[104mCol 1 Row 2\x1b[49m\x1b[0m\x1b[104m     \x1b[49m\x1b[0m\x1b[104m  \x1b[49m\x1b[0m\x1b[104mCol 2 Row 2\x1b[49m\x1b[0m\x1b[104m     \x1b[49m\x1b[0m'
    )

    # Make sure SimpleTable respects style_header_text and style_data_text flags.
    # Don't apply parent table's background colors to header or data text in second column.
    st = SimpleTable([column_1, Column("Col 2", width=16, style_header_text=False, style_data_text=False)],
                     divider_char=None, header_bg=Bg.GREEN, data_bg=Bg.LIGHT_BLUE)
    table = st.generate_table(row_data)
    assert table == (
        '\x1b[0m\x1b[42mCol 1\x1b[49m\x1b[0m\x1b[42m           \x1b[49m\x1b[0m\x1b[42m  \x1b[49m\x1b[0mCol 2\x1b[0m\x1b[42m           \x1b[49m\x1b[0m\n'
        '\x1b[0m\x1b[104mCol 1 Row 1\x1b[49m\x1b[0m\x1b[104m     \x1b[49m\x1b[0m\x1b[104m  \x1b[49m\x1b[0mCol 2 Row 1\x1b[0m\x1b[104m     \x1b[49m\x1b[0m\n'
        '\x1b[0m\x1b[0m\x1b[104m                                  \x1b[49m\x1b[0m\n'
        '\x1b[0m\x1b[104mCol 1 Row 2\x1b[49m\x1b[0m\x1b[104m     \x1b[49m\x1b[0m\x1b[104m  \x1b[49m\x1b[0mCol 2 Row 2\x1b[0m\x1b[104m     \x1b[49m\x1b[0m'
    )


def test_simple_table_width():
    # Base width
    for num_cols in range(1, 10):
        assert SimpleTable.base_width(num_cols) == (num_cols - 1) * 2

    # Invalid num_cols value
    with pytest.raises(ValueError) as excinfo:
        SimpleTable.base_width(0)
    assert "Column count cannot be less than 1" in str(excinfo.value)

    # Total width
    column_1 = Column("Col 1", width=16)
    column_2 = Column("Col 2", width=16)

    row_data = list()
    row_data.append(["Col 1 Row 1", "Col 2 Row 1"])
    row_data.append(["Col 1 Row 2", "Col 2 Row 2"])

    st = SimpleTable([column_1, column_2])
    assert st.total_width() == 34


def test_simple_generate_data_row_exceptions():
    column_1 = Column("Col 1")
    tc = SimpleTable([column_1])

    # Data with too many columns
    row_data = ['Data 1', 'Extra Column']
    with pytest.raises(ValueError) as excinfo:
        tc.generate_data_row(row_data=row_data)
    assert "Length of row_data must match length of cols" in str(excinfo.value)


def test_bordered_table_creation():
    column_1 = Column("Col 1", width=15)
    column_2 = Column("Col 2", width=15)

    row_data = list()
    row_data.append(["Col 1 Row 1", "Col 2 Row 1"])
    row_data.append(["Col 1 Row 2", "Col 2 Row 2"])

    # Default options
    bt = BorderedTable([column_1, column_2])
    table = bt.generate_table(row_data)
    assert table == (
        '╔═════════════════╤═════════════════╗\n'
        '║ Col 1           │ Col 2           ║\n'
        '╠═════════════════╪═════════════════╣\n'
        '║ Col 1 Row 1     │ Col 2 Row 1     ║\n'
        '╟─────────────────┼─────────────────╢\n'
        '║ Col 1 Row 2     │ Col 2 Row 2     ║\n'
        '╚═════════════════╧═════════════════╝'
    )

    # No column borders
    bt = BorderedTable([column_1, column_2], column_borders=False)
    table = bt.generate_table(row_data)
    assert table == (
        '╔══════════════════════════════════╗\n'
        '║ Col 1            Col 2           ║\n'
        '╠══════════════════════════════════╣\n'
        '║ Col 1 Row 1      Col 2 Row 1     ║\n'
        '╟──────────────────────────────────╢\n'
        '║ Col 1 Row 2      Col 2 Row 2     ║\n'
        '╚══════════════════════════════════╝'
    )

    # No header
    bt = BorderedTable([column_1, column_2])
    table = bt.generate_table(row_data, include_header=False)
    assert table == (
        '╔═════════════════╤═════════════════╗\n'
        '║ Col 1 Row 1     │ Col 2 Row 1     ║\n'
        '╟─────────────────┼─────────────────╢\n'
        '║ Col 1 Row 2     │ Col 2 Row 2     ║\n'
        '╚═════════════════╧═════════════════╝'
    )

    # Non-default padding
    bt = BorderedTable([column_1, column_2], padding=2)
    table = bt.generate_table(row_data)
    assert table == (
        '╔═══════════════════╤═══════════════════╗\n'
        '║  Col 1            │  Col 2            ║\n'
        '╠═══════════════════╪═══════════════════╣\n'
        '║  Col 1 Row 1      │  Col 2 Row 1      ║\n'
        '╟───────────────────┼───────────────────╢\n'
        '║  Col 1 Row 2      │  Col 2 Row 2      ║\n'
        '╚═══════════════════╧═══════════════════╝'
    )

    # Invalid padding
    with pytest.raises(ValueError) as excinfo:
        BorderedTable([column_1, column_2], padding=-1)
    assert "Padding cannot be less than 0" in str(excinfo.value)

    # Test border, header, and data colors
    bt = BorderedTable([column_1, column_2], border_fg=Fg.LIGHT_YELLOW, border_bg=Bg.WHITE,
                       header_bg=Bg.GREEN, data_bg=Bg.LIGHT_BLUE)
    table = bt.generate_table(row_data)
    assert table == (
        '\x1b[93m\x1b[107m╔═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╤═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╗\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\x1b[42m \x1b[49m\x1b[0m\x1b[42mCol 1\x1b[49m\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m\x1b[93m\x1b[107m│\x1b[39m\x1b[49m\x1b[42m \x1b[49m\x1b[0m\x1b[42mCol 2\x1b[49m\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m╠═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╪═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╣\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 1 Row 1\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m\x1b[93m\x1b[107m│\x1b[39m\x1b[49m\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 2 Row 1\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m╟─\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m───────────────\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m─┼─\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m───────────────\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m─╢\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 1 Row 2\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m\x1b[93m\x1b[107m│\x1b[39m\x1b[49m\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 2 Row 2\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m╚═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╧═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╝\x1b[39m\x1b[49m'
    )

    # Make sure BorderedTable respects style_header_text and style_data_text flags.
    # Don't apply parent table's background colors to header or data text in second column.
    bt = BorderedTable([column_1, Column("Col 2", width=15, style_header_text=False, style_data_text=False)],
                       header_bg=Bg.GREEN, data_bg=Bg.LIGHT_BLUE)
    table = bt.generate_table(row_data)
    assert table == (
        '╔═════════════════╤═════════════════╗\n'
        '║\x1b[42m \x1b[49m\x1b[0m\x1b[42mCol 1\x1b[49m\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m│\x1b[42m \x1b[49m\x1b[0mCol 2\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m║\n'
        '╠═════════════════╪═════════════════╣\n'
        '║\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 1 Row 1\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m│\x1b[104m \x1b[49m\x1b[0mCol 2 Row 1\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m║\n'
        '╟─────────────────┼─────────────────╢\n'
        '║\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 1 Row 2\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m│\x1b[104m \x1b[49m\x1b[0mCol 2 Row 2\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m║\n'
        '╚═════════════════╧═════════════════╝'
    )


def test_bordered_table_width():
    # Default behavior (column_borders=True, padding=1)
    assert BorderedTable.base_width(1) == 4
    assert BorderedTable.base_width(2) == 7
    assert BorderedTable.base_width(3) == 10

    # No column borders
    assert BorderedTable.base_width(1, column_borders=False) == 4
    assert BorderedTable.base_width(2, column_borders=False) == 6
    assert BorderedTable.base_width(3, column_borders=False) == 8

    # No padding
    assert BorderedTable.base_width(1, padding=0) == 2
    assert BorderedTable.base_width(2, padding=0) == 3
    assert BorderedTable.base_width(3, padding=0) == 4

    # Extra padding
    assert BorderedTable.base_width(1, padding=3) == 8
    assert BorderedTable.base_width(2, padding=3) == 15
    assert BorderedTable.base_width(3, padding=3) == 22

    # Invalid num_cols value
    with pytest.raises(ValueError) as excinfo:
        BorderedTable.base_width(0)
    assert "Column count cannot be less than 1" in str(excinfo.value)

    # Total width
    column_1 = Column("Col 1", width=15)
    column_2 = Column("Col 2", width=15)

    row_data = list()
    row_data.append(["Col 1 Row 1", "Col 2 Row 1"])
    row_data.append(["Col 1 Row 2", "Col 2 Row 2"])

    bt = BorderedTable([column_1, column_2])
    assert bt.total_width() == 37


def test_bordered_generate_data_row_exceptions():
    column_1 = Column("Col 1")
    tc = BorderedTable([column_1])

    # Data with too many columns
    row_data = ['Data 1', 'Extra Column']
    with pytest.raises(ValueError) as excinfo:
        tc.generate_data_row(row_data=row_data)
    assert "Length of row_data must match length of cols" in str(excinfo.value)


def test_alternating_table_creation():
    column_1 = Column("Col 1", width=15)
    column_2 = Column("Col 2", width=15)

    row_data = list()
    row_data.append(["Col 1 Row 1", "Col 2 Row 1"])
    row_data.append(["Col 1 Row 2", "Col 2 Row 2"])

    # Default options
    at = AlternatingTable([column_1, column_2])
    table = at.generate_table(row_data)
    assert table == (
        '╔═════════════════╤═════════════════╗\n'
        '║ Col 1           │ Col 2           ║\n'
        '╠═════════════════╪═════════════════╣\n'
        '║ Col 1 Row 1     │ Col 2 Row 1     ║\n'
        '║\x1b[100m \x1b[49m\x1b[0m\x1b[100mCol 1 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m \x1b[49m│\x1b[100m \x1b[49m\x1b[0m\x1b[100mCol 2 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m \x1b[49m║\n'
        '╚═════════════════╧═════════════════╝'
    )

    # No column borders
    at = AlternatingTable([column_1, column_2], column_borders=False)
    table = at.generate_table(row_data)
    assert table == (
        '╔══════════════════════════════════╗\n'
        '║ Col 1            Col 2           ║\n'
        '╠══════════════════════════════════╣\n'
        '║ Col 1 Row 1      Col 2 Row 1     ║\n'
        '║\x1b[100m \x1b[49m\x1b[0m\x1b[100mCol 1 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m \x1b[49m\x1b[100m \x1b[49m\x1b[0m\x1b[100mCol 2 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m \x1b[49m║\n'
        '╚══════════════════════════════════╝'
    )

    # No header
    at = AlternatingTable([column_1, column_2])
    table = at.generate_table(row_data, include_header=False)
    assert table == (
        '╔═════════════════╤═════════════════╗\n'
        '║ Col 1 Row 1     │ Col 2 Row 1     ║\n'
        '║\x1b[100m \x1b[49m\x1b[0m\x1b[100mCol 1 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m \x1b[49m│\x1b[100m \x1b[49m\x1b[0m\x1b[100mCol 2 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m \x1b[49m║\n'
        '╚═════════════════╧═════════════════╝'
    )

    # Non-default padding
    at = AlternatingTable([column_1, column_2], padding=2)
    table = at.generate_table(row_data)
    assert table == (
        '╔═══════════════════╤═══════════════════╗\n'
        '║  Col 1            │  Col 2            ║\n'
        '╠═══════════════════╪═══════════════════╣\n'
        '║  Col 1 Row 1      │  Col 2 Row 1      ║\n'
        '║\x1b[100m  \x1b[49m\x1b[0m\x1b[100mCol 1 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m  \x1b[49m│\x1b[100m  \x1b[49m\x1b[0m\x1b[100mCol 2 Row 2\x1b[49m\x1b[0m\x1b[100m    \x1b[49m\x1b[0m\x1b[100m  \x1b[49m║\n'
        '╚═══════════════════╧═══════════════════╝'
    )

    # Invalid padding
    with pytest.raises(ValueError) as excinfo:
        AlternatingTable([column_1, column_2], padding=-1)
    assert "Padding cannot be less than 0" in str(excinfo.value)

    # Test border, header, and data colors
    at = AlternatingTable([column_1, column_2], border_fg=Fg.LIGHT_YELLOW, border_bg=Bg.WHITE,
                          header_bg=Bg.GREEN, odd_bg=Bg.LIGHT_BLUE, even_bg=Bg.LIGHT_RED)
    table = at.generate_table(row_data)
    assert table == (
        '\x1b[93m\x1b[107m╔═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╤═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╗\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\x1b[42m \x1b[49m\x1b[0m\x1b[42mCol 1\x1b[49m\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m\x1b[93m\x1b[107m│\x1b[39m\x1b[49m\x1b[42m \x1b[49m\x1b[0m\x1b[42mCol 2\x1b[49m\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m╠═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╪═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╣\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 1 Row 1\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m\x1b[93m\x1b[107m│\x1b[39m\x1b[49m\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 2 Row 1\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\x1b[101m \x1b[49m\x1b[0m\x1b[101mCol 1 Row 2\x1b[49m\x1b[0m\x1b[101m    \x1b[49m\x1b[0m\x1b[101m \x1b[49m\x1b[93m\x1b[107m│\x1b[39m\x1b[49m\x1b[101m \x1b[49m\x1b[0m\x1b[101mCol 2 Row 2\x1b[49m\x1b[0m\x1b[101m    \x1b[49m\x1b[0m\x1b[101m \x1b[49m\x1b[93m\x1b[107m║\x1b[39m\x1b[49m\n'
        '\x1b[93m\x1b[107m╚═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╧═\x1b[39m\x1b[49m\x1b[0m\x1b[0m\x1b[93m\x1b[107m═══════════════\x1b[39m\x1b[49m\x1b[0m\x1b[93m\x1b[107m═╝\x1b[39m\x1b[49m'
    )

    # Make sure AlternatingTable respects style_header_text and style_data_text flags.
    # Don't apply parent table's background colors to header or data text in second column.
    at = AlternatingTable([column_1, Column("Col 2", width=15, style_header_text=False, style_data_text=False)],
                          header_bg=Bg.GREEN, odd_bg=Bg.LIGHT_BLUE, even_bg=Bg.LIGHT_RED)
    table = at.generate_table(row_data)
    assert table == (
        '╔═════════════════╤═════════════════╗\n'
        '║\x1b[42m \x1b[49m\x1b[0m\x1b[42mCol 1\x1b[49m\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m│\x1b[42m \x1b[49m\x1b[0mCol 2\x1b[0m\x1b[42m          \x1b[49m\x1b[0m\x1b[42m \x1b[49m║\n'
        '╠═════════════════╪═════════════════╣\n'
        '║\x1b[104m \x1b[49m\x1b[0m\x1b[104mCol 1 Row 1\x1b[49m\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m│\x1b[104m \x1b[49m\x1b[0mCol 2 Row 1\x1b[0m\x1b[104m    \x1b[49m\x1b[0m\x1b[104m \x1b[49m║\n'
        '║\x1b[101m \x1b[49m\x1b[0m\x1b[101mCol 1 Row 2\x1b[49m\x1b[0m\x1b[101m    \x1b[49m\x1b[0m\x1b[101m \x1b[49m│\x1b[101m \x1b[49m\x1b[0mCol 2 Row 2\x1b[0m\x1b[101m    \x1b[49m\x1b[0m\x1b[101m \x1b[49m║\n'
        '╚═════════════════╧═════════════════╝'
    )
