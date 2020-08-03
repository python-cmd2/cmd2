# coding=utf-8
"""
cmd2 table creation API
This API is built upon two core classes: Column and TableCreator
The general use case is to inherit from TableCreator to create a table class with custom formatting options.
There are already implemented and ready-to-use examples of this below TableCreator's code.
"""
import copy
import functools
import io
from collections import deque
from enum import Enum
from typing import Any, Optional, Sequence, Tuple, Union

from wcwidth import wcwidth

from . import ansi, constants, utils

# This is needed for compatibility with early versions of Python 3.5 prior to 3.5.4
try:
    from typing import Deque
except ImportError:  # pragma: no cover
    import typing

    # noinspection PyProtectedMember, PyUnresolvedReferences
    Deque = typing._alias(deque, typing.T)

# Constants
EMPTY = ''
SPACE = ' '


class HorizontalAlignment(Enum):
    """Horizontal alignment of text in a cell"""
    LEFT = 1
    CENTER = 2
    RIGHT = 3


class VerticalAlignment(Enum):
    """Vertical alignment of text in a cell"""
    TOP = 1
    MIDDLE = 2
    BOTTOM = 3


class Column:
    """Table column configuration"""
    def __init__(self, header: str, *, width: Optional[int] = None,
                 header_horiz_align: HorizontalAlignment = HorizontalAlignment.LEFT,
                 header_vert_align: VerticalAlignment = VerticalAlignment.BOTTOM,
                 data_horiz_align: HorizontalAlignment = HorizontalAlignment.LEFT,
                 data_vert_align: VerticalAlignment = VerticalAlignment.TOP,
                 max_data_lines: Union[int, float] = constants.INFINITY) -> None:
        """
        Column initializer

        :param header: label for column header
        :param width: display width of column. This does not account for any borders or padding which
                      may be added (e.g pre_line, inter_cell, and post_line). Header and data text wrap within
                      this width using word-based wrapping (defaults to width of header or 1 if header is blank)
        :param header_horiz_align: horizontal alignment of header cells (defaults to left)
        :param header_vert_align: vertical alignment of header cells (defaults to bottom)
        :param data_horiz_align: horizontal alignment of data cells (defaults to left)
        :param data_vert_align: vertical alignment of data cells (defaults to top)
        :param max_data_lines: maximum lines allowed in a data cell. If line count exceeds this, then the final
                               line displayed will be truncated with an ellipsis. (defaults to INFINITY)
        :raises: ValueError if width is less than 1
        :raises: ValueError if max_data_lines is less than 1
        """
        self.header = header

        if width is None:
            # Use the width of the widest line in the header or 1 if the header has no width
            line_widths = [ansi.style_aware_wcswidth(line) for line in self.header.splitlines()]
            line_widths.append(1)
            self.width = max(line_widths)
        elif width < 1:
            raise ValueError("Column width cannot be less than 1")
        else:
            self.width = width

        self.header_horiz_align = header_horiz_align
        self.header_vert_align = header_vert_align
        self.data_horiz_align = data_horiz_align
        self.data_vert_align = data_vert_align

        if max_data_lines < 1:
            raise ValueError("Max data lines cannot be less than 1")

        self.max_data_lines = max_data_lines


class TableCreator:
    """
    Base table creation class. This class handles ANSI style sequences and characters with display widths greater than 1
    when performing width calculations. It was designed with the ability to build tables one row at a time. This helps
    when you have large data sets that you don't want to hold in memory or when you receive portions of the data set
    incrementally.

    TableCreator has one public method: generate_row()

    This function and the Column class provide all features needed to build tables with headers, borders, colors,
    horizontal and vertical alignment, and wrapped text. However, it's generally easier to inherit from this class and
    implement a more granular API rather than use TableCreator directly. There are ready-to-use examples of this
    defined after this class.
    """
    def __init__(self, cols: Sequence[Column], *, tab_width: int = 4) -> None:
        """
        TableCreator initializer

        :param cols: column definitions for this table
        :param tab_width: all tabs will be replaced with this many spaces. If a row's fill_char is a tab,
                          then it will be converted to one space.
        """
        self.cols = copy.copy(cols)
        self.tab_width = tab_width

    @staticmethod
    def _wrap_long_word(word: str, max_width: int, max_lines: Union[int, float], is_last_word: bool) -> Tuple[str, int, int]:
        """
        Used by _wrap_text() to wrap a long word over multiple lines

        :param word: word being wrapped
        :param max_width: maximum display width of a line
        :param max_lines: maximum lines to wrap before ending the last line displayed with an ellipsis
        :param is_last_word: True if this is the last word of the total text being wrapped
        :return: Tuple(wrapped text, lines used, display width of last line)
        """
        styles = utils.get_styles_in_text(word)
        wrapped_buf = io.StringIO()

        # How many lines we've used
        total_lines = 1

        # Display width of the current line we are building
        cur_line_width = 0

        char_index = 0
        while char_index < len(word):
            # We've reached the last line. Let truncate_line do the rest.
            if total_lines == max_lines:
                # If this isn't the last word, but it's gonna fill the final line, then force truncate_line
                # to place an ellipsis at the end of it by making the word too wide.
                remaining_word = word[char_index:]
                if not is_last_word and ansi.style_aware_wcswidth(remaining_word) == max_width:
                    remaining_word += "EXTRA"

                truncated_line = utils.truncate_line(remaining_word, max_width)
                cur_line_width = ansi.style_aware_wcswidth(truncated_line)
                wrapped_buf.write(truncated_line)
                break

            # Check if we're at a style sequence. These don't count toward display width.
            if char_index in styles:
                wrapped_buf.write(styles[char_index])
                char_index += len(styles[char_index])
                continue

            cur_char = word[char_index]
            cur_char_width = wcwidth(cur_char)

            if cur_char_width > max_width:
                # We have a case where the character is wider than max_width. This can happen if max_width
                # is 1 and the text contains wide characters (e.g. East Asian). Replace it with an ellipsis.
                cur_char = constants.HORIZONTAL_ELLIPSIS
                cur_char_width = wcwidth(cur_char)

            if cur_line_width + cur_char_width > max_width:
                # Adding this char will exceed the max_width. Start a new line.
                wrapped_buf.write('\n')
                total_lines += 1
                cur_line_width = 0
                continue

            # Add this character and move to the next one
            cur_line_width += cur_char_width
            wrapped_buf.write(cur_char)
            char_index += 1

        return wrapped_buf.getvalue(), total_lines, cur_line_width

    @staticmethod
    def _wrap_text(text: str, max_width: int, max_lines: Union[int, float]) -> str:
        """
        Wrap text into lines with a display width no longer than max_width. This function breaks words on whitespace
        boundaries. If a word is longer than the space remaining on a line, then it will start on a new line.
        ANSI escape sequences do not count toward the width of a line.

        :param text: text to be wrapped
        :param max_width: maximum display width of a line
        :param max_lines: maximum lines to wrap before ending the last line displayed with an ellipsis
        :return: wrapped text
        """
        def add_word(word_to_add: str, is_last_word: bool):
            """
            Called from loop to add a word to the wrapped text

            :param word_to_add: the word being added
            :param is_last_word: True if this is the last word of the total text being wrapped
            """
            nonlocal cur_line_width
            nonlocal total_lines

            # No more space to add word
            if total_lines == max_lines and cur_line_width == max_width:
                return

            word_width = ansi.style_aware_wcswidth(word_to_add)

            # If the word is wider than max width of a line, attempt to start it on its own line and wrap it
            if word_width > max_width:
                room_to_add = True

                if cur_line_width > 0:
                    # The current line already has text, check if there is room to create a new line
                    if total_lines < max_lines:
                        wrapped_buf.write('\n')
                        total_lines += 1
                    else:
                        # We will truncate this word on the remaining line
                        room_to_add = False

                if room_to_add:
                    wrapped_word, lines_used, cur_line_width = TableCreator._wrap_long_word(word_to_add,
                                                                                            max_width,
                                                                                            max_lines - total_lines + 1,
                                                                                            is_last_word)
                    # Write the word to the buffer
                    wrapped_buf.write(wrapped_word)
                    total_lines += lines_used - 1
                    return

            # We aren't going to wrap the word across multiple lines
            remaining_width = max_width - cur_line_width

            # Check if we need to start a new line
            if word_width > remaining_width and total_lines < max_lines:
                # Save the last character in wrapped_buf, which can't be empty at this point.
                seek_pos = wrapped_buf.tell() - 1
                wrapped_buf.seek(seek_pos)
                last_char = wrapped_buf.read()

                wrapped_buf.write('\n')
                total_lines += 1
                cur_line_width = 0
                remaining_width = max_width

                # Only when a space is following a space do we want to start the next line with it.
                if word_to_add == SPACE and last_char != SPACE:
                    return

            # Check if we've hit the last line we're allowed to create
            if total_lines == max_lines:
                # If this word won't fit, truncate it
                if word_width > remaining_width:
                    word_to_add = utils.truncate_line(word_to_add, remaining_width)
                    word_width = remaining_width

                # If this isn't the last word, but it's gonna fill the final line, then force truncate_line
                # to place an ellipsis at the end of it by making the word too wide.
                elif not is_last_word and word_width == remaining_width:
                    word_to_add = utils.truncate_line(word_to_add + "EXTRA", remaining_width)

            cur_line_width += word_width
            wrapped_buf.write(word_to_add)

        ############################################################################################################
        # _wrap_text() main code
        ############################################################################################################
        # Buffer of the wrapped text
        wrapped_buf = io.StringIO()

        # How many lines we've used
        total_lines = 0

        # Respect the existing line breaks
        data_str_lines = text.splitlines()
        for data_line_index, data_line in enumerate(data_str_lines):
            total_lines += 1

            if data_line_index > 0:
                wrapped_buf.write('\n')

            # Locate the styles in this line
            styles = utils.get_styles_in_text(data_line)

            # Display width of the current line we are building
            cur_line_width = 0

            # Current word being built
            cur_word_buf = io.StringIO()

            char_index = 0
            while char_index < len(data_line):
                if total_lines == max_lines and cur_line_width == max_width:
                    break

                # Check if we're at a style sequence. These don't count toward display width.
                if char_index in styles:
                    cur_word_buf.write(styles[char_index])
                    char_index += len(styles[char_index])
                    continue

                cur_char = data_line[char_index]
                if cur_char == SPACE:
                    # If we've reached the end of a word, then add the word to the wrapped text
                    if cur_word_buf.tell() > 0:
                        # is_last_word is False since there is a space after the word
                        add_word(cur_word_buf.getvalue(), is_last_word=False)
                        cur_word_buf = io.StringIO()

                    # Add the space to the wrapped text
                    last_word = data_line_index == len(data_str_lines) - 1 and char_index == len(data_line) - 1
                    add_word(cur_char, last_word)
                else:
                    # Add this character to the word buffer
                    cur_word_buf.write(cur_char)

                char_index += 1

            # Add the final word of this line if it's been started
            if cur_word_buf.tell() > 0:
                last_word = data_line_index == len(data_str_lines) - 1 and char_index == len(data_line)
                add_word(cur_word_buf.getvalue(), last_word)

            # Stop line loop if we've written to max_lines
            if total_lines == max_lines:
                # If this isn't the last data line and there is space left on the final wrapped line, then add an ellipsis
                if data_line_index < len(data_str_lines) - 1 and cur_line_width < max_width:
                    wrapped_buf.write(constants.HORIZONTAL_ELLIPSIS)
                break

        return wrapped_buf.getvalue()

    def _generate_cell_lines(self, cell_data: Any, is_header: bool, col: Column, fill_char: str) -> Tuple[Deque[str], int]:
        """
        Generate the lines of a table cell

        :param cell_data: data to be included in cell
        :param is_header: True if writing a header cell, otherwise writing a data cell
        :param col: Column definition for this cell
        :param fill_char: character that fills remaining space in a cell. If your text has a background color,
                          then give fill_char the same background color. (Cannot be a line breaking character)
        :return: Tuple of cell lines deque and the display width of the cell
        """
        # Convert data to string and replace tabs with spaces
        data_str = str(cell_data).replace('\t', SPACE * self.tab_width)

        # Wrap text in this cell
        max_lines = constants.INFINITY if is_header else col.max_data_lines
        wrapped_text = self._wrap_text(data_str, col.width, max_lines)

        # Align the text horizontally
        horiz_alignment = col.header_horiz_align if is_header else col.data_horiz_align
        if horiz_alignment == HorizontalAlignment.LEFT:
            text_alignment = utils.TextAlignment.LEFT
        elif horiz_alignment == HorizontalAlignment.CENTER:
            text_alignment = utils.TextAlignment.CENTER
        else:
            text_alignment = utils.TextAlignment.RIGHT

        aligned_text = utils.align_text(wrapped_text, fill_char=fill_char, width=col.width, alignment=text_alignment)

        lines = deque(aligned_text.splitlines())
        cell_width = max([ansi.style_aware_wcswidth(line) for line in lines])
        return lines, cell_width

    def generate_row(self, *, row_data: Optional[Sequence[Any]] = None, fill_char: str = SPACE,
                     pre_line: str = EMPTY, inter_cell: str = (2 * SPACE), post_line: str = EMPTY) -> str:
        """
        Generate a header or data table row

        :param row_data: If this is None then a header row is generated. Otherwise data should have an entry for each
                         column in the row. (Defaults to None)
        :param fill_char: character that fills remaining space in a cell. Defaults to space. If this is a tab, then it will
                          be converted to one space. (Cannot be a line breaking character)
        :param pre_line: string to print before each line of a row. This can be used for a left row border and
                         padding before the first cell's text. (Defaults to blank)
        :param inter_cell: string to print where two cells meet. This can be used for a border between cells and padding
                           between it and the 2 cells' text. (Defaults to 2 spaces)
        :param post_line: string to print after each line of a row. This can be used for padding after the last cell's text
                          and a right row border. (Defaults to blank)
        :return: row string
        :raises: ValueError if data isn't the same length as self.cols
        :raises: TypeError if fill_char is more than one character (not including ANSI style sequences)
        :raises: ValueError if fill_char, pre_line, inter_cell, or post_line contains an unprintable
                 character like a newline
        """
        class Cell:
            """Inner class which represents a table cell"""
            def __init__(self) -> None:
                # Data in this cell split into individual lines
                self.lines = []

                # Display width of this cell
                self.width = 0

        if row_data is None:
            row_data = [col.header for col in self.cols]
            is_header = True
        else:
            if len(row_data) != len(self.cols):
                raise ValueError("Length of row_data must match length of cols")
            is_header = False

        # Replace tabs (tabs in data strings will be handled in _generate_cell_lines())
        fill_char = fill_char.replace('\t', SPACE)
        pre_line = pre_line.replace('\t', SPACE * self.tab_width)
        inter_cell = inter_cell.replace('\t', SPACE * self.tab_width)
        post_line = post_line.replace('\t', SPACE * self.tab_width)

        # Validate fill_char character count
        if len(ansi.strip_style(fill_char)) != 1:
            raise TypeError("Fill character must be exactly one character long")

        # Look for unprintable characters
        validation_dict = {'fill_char': fill_char, 'pre_line': pre_line,
                           'inter_cell': inter_cell, 'post_line': post_line}
        for key, val in validation_dict.items():
            if ansi.style_aware_wcswidth(val) == -1:
                raise (ValueError("{} contains an unprintable character".format(key)))

        # Number of lines this row uses
        total_lines = 0

        # Generate the cells for this row
        cells = list()

        for col_index, col in enumerate(self.cols):
            cell = Cell()
            cell.lines, cell.width = self._generate_cell_lines(row_data[col_index], is_header, col, fill_char)
            cells.append(cell)
            total_lines = max(len(cell.lines), total_lines)

        row_buf = io.StringIO()

        # Vertically align each cell
        for cell_index, cell in enumerate(cells):
            col = self.cols[cell_index]
            vert_align = col.header_vert_align if is_header else col.data_vert_align

            # Check if this cell need vertical filler
            line_diff = total_lines - len(cell.lines)
            if line_diff == 0:
                continue

            # Add vertical filler lines
            padding_line = utils.align_left(EMPTY, fill_char=fill_char, width=cell.width)
            if vert_align == VerticalAlignment.TOP:
                to_top = 0
                to_bottom = line_diff
            elif vert_align == VerticalAlignment.MIDDLE:
                to_top = line_diff // 2
                to_bottom = line_diff - to_top
            else:
                to_top = line_diff
                to_bottom = 0

            for i in range(to_top):
                cell.lines.appendleft(padding_line)
            for i in range(to_bottom):
                cell.lines.append(padding_line)

        # Build this row one line at a time
        for line_index in range(total_lines):
            for cell_index, cell in enumerate(cells):
                if cell_index == 0:
                    row_buf.write(pre_line)

                row_buf.write(cell.lines[line_index])

                if cell_index < len(self.cols) - 1:
                    row_buf.write(inter_cell)
                if cell_index == len(self.cols) - 1:
                    row_buf.write(post_line)

            # Add a newline if this is not the last line
            if line_index < total_lines - 1:
                row_buf.write('\n')

        return row_buf.getvalue()


############################################################################################################
# The following are implementations of TableCreator which demonstrate how to make various types
# of tables. They can be used as-is or serve as inspiration for other custom table classes.
############################################################################################################
class SimpleTable(TableCreator):
    """
    Implementation of TableCreator which generates a borderless table with an optional divider row after the header.
    This class can be used to create the whole table at once or one row at a time.
    """
    # Spaces between cells
    INTER_CELL = 2 * SPACE

    def __init__(self, cols: Sequence[Column], *, tab_width: int = 4, divider_char: Optional[str] = '-') -> None:
        """
        SimpleTable initializer

        :param cols: column definitions for this table
        :param tab_width: all tabs will be replaced with this many spaces. If a row's fill_char is a tab,
                          then it will be converted to one space.
        :param divider_char: optional character used to build the header divider row. Set this to None if you don't
                             want a divider row. Defaults to dash. (Cannot be a line breaking character)
        :raises: TypeError if fill_char is more than one character (not including ANSI style sequences)
        :raises: ValueError if text or fill_char contains an unprintable character
        """
        if divider_char is not None:
            if len(ansi.strip_style(divider_char)) != 1:
                raise TypeError("Divider character must be exactly one character long")

            divider_char_width = ansi.style_aware_wcswidth(divider_char)
            if divider_char_width == -1:
                raise (ValueError("Divider character is an unprintable character"))

        super().__init__(cols, tab_width=tab_width)
        self.divider_char = divider_char

    @classmethod
    def base_width(cls, num_cols: int) -> int:
        """
        Utility method to calculate the display width required for a table before data is added to it.
        This is useful when determining how wide to make your columns to have a table be a specific width.

        :param num_cols: how many columns the table will have
        :return: base width
        :raises: ValueError if num_cols is less than 1
        """
        if num_cols < 1:
            raise ValueError("Column count cannot be less than 1")

        data_str = SPACE
        data_width = ansi.style_aware_wcswidth(data_str) * num_cols

        tbl = cls([Column(data_str)] * num_cols)
        data_row = tbl.generate_data_row([data_str] * num_cols)

        return ansi.style_aware_wcswidth(data_row) - data_width

    def total_width(self) -> int:
        """Calculate the total display width of this table"""
        base_width = self.base_width(len(self.cols))
        data_width = sum(col.width for col in self.cols)
        return base_width + data_width

    def generate_header(self) -> str:
        """Generate table header with an optional divider row"""
        header_buf = io.StringIO()

        # Create the header labels
        header = self.generate_row(inter_cell=self.INTER_CELL)
        header_buf.write(header)

        # Create the divider if necessary
        if self.divider_char is not None:
            total_width = self.total_width()
            divider_char_width = ansi.style_aware_wcswidth(self.divider_char)

            # Make divider as wide as table and use padding if width of
            # divider_char does not divide evenly into table width.
            divider = self.divider_char * (total_width // divider_char_width)
            divider += SPACE * (total_width % divider_char_width)

            header_buf.write('\n')
            header_buf.write(divider)
        return header_buf.getvalue()

    def generate_data_row(self, row_data: Sequence[Any]) -> str:
        """
        Generate a data row

        :param row_data: data with an entry for each column in the row
        :return: data row string
        """
        return self.generate_row(row_data=row_data, inter_cell=self.INTER_CELL)

    def generate_table(self, table_data: Sequence[Sequence[Any]], *,
                       include_header: bool = True, row_spacing: int = 1) -> str:
        """
        Generate a table from a data set

        :param table_data: Data with an entry for each data row of the table. Each entry should have data for
                           each column in the row.
        :param include_header: If True, then a header will be included at top of table. (Defaults to True)
        :param row_spacing: A number 0 or greater specifying how many blank lines to place between each row (Defaults to 1)
        :raises: ValueError if row_spacing is less than 0
        """
        if row_spacing < 0:
            raise ValueError("Row spacing cannot be less than 0")

        table_buf = io.StringIO()

        if include_header:
            header = self.generate_header()
            table_buf.write(header)
            if len(table_data) > 0:
                table_buf.write('\n')

        for index, row_data in enumerate(table_data):
            if index > 0 and row_spacing > 0:
                table_buf.write(row_spacing * '\n')

            row = self.generate_data_row(row_data)
            table_buf.write(row)
            if index < len(table_data) - 1:
                table_buf.write('\n')

        return table_buf.getvalue()


class BorderedTable(TableCreator):
    """
    Implementation of TableCreator which generates a table with borders around the table and between rows. Borders
    between columns can also be toggled. This class can be used to create the whole table at once or one row at a time.
    """
    def __init__(self, cols: Sequence[Column], *, tab_width: int = 4,
                 column_borders: bool = True, padding: int = 1) -> None:
        """
        BorderedTable initializer

        :param cols: column definitions for this table
        :param tab_width: all tabs will be replaced with this many spaces. If a row's fill_char is a tab,
                          then it will be converted to one space.
        :param column_borders: if True, borders between columns will be included. This gives the table a grid-like
                               appearance. Turning off column borders results in a unified appearance between
                               a row's cells. (Defaults to True)
        :param padding: number of spaces between text and left/right borders of cell
        :raises: ValueError if padding is less than 0
        """
        super().__init__(cols, tab_width=tab_width)
        self.empty_data = [EMPTY for _ in self.cols]
        self.column_borders = column_borders

        if padding < 0:
            raise ValueError("Padding cannot be less than 0")
        self.padding = padding

    @classmethod
    def base_width(cls, num_cols: int, *, column_borders: bool = True, padding: int = 1) -> int:
        """
        Utility method to calculate the display width required for a table before data is added to it.
        This is useful when determining how wide to make your columns to have a table be a specific width.

        :param num_cols: how many columns the table will have
        :param column_borders: if True, borders between columns will be included in the calculation (Defaults to True)
        :param padding: number of spaces between text and left/right borders of cell
        :return: base width
        :raises: ValueError if num_cols is less than 1
        """
        if num_cols < 1:
            raise ValueError("Column count cannot be less than 1")

        data_str = SPACE
        data_width = ansi.style_aware_wcswidth(data_str) * num_cols

        tbl = cls([Column(data_str)] * num_cols, column_borders=column_borders, padding=padding)
        data_row = tbl.generate_data_row([data_str] * num_cols)

        return ansi.style_aware_wcswidth(data_row) - data_width

    def total_width(self) -> int:
        """Calculate the total display width of this table"""
        base_width = self.base_width(len(self.cols), column_borders=self.column_borders, padding=self.padding)
        data_width = sum(col.width for col in self.cols)
        return base_width + data_width

    def generate_table_top_border(self):
        """Generate a border which appears at the top of the header and data section"""
        pre_line = '╔' + self.padding * '═'

        inter_cell = self.padding * '═'
        if self.column_borders:
            inter_cell += "╤"
        inter_cell += self.padding * '═'

        post_line = self.padding * '═' + '╗'

        return self.generate_row(row_data=self.empty_data, fill_char='═', pre_line=pre_line,
                                 inter_cell=inter_cell, post_line=post_line)

    def generate_header_bottom_border(self):
        """Generate a border which appears at the bottom of the header"""
        pre_line = '╠' + self.padding * '═'

        inter_cell = self.padding * '═'
        if self.column_borders:
            inter_cell += '╪'
        inter_cell += self.padding * '═'

        post_line = self.padding * '═' + '╣'

        return self.generate_row(row_data=self.empty_data, fill_char='═', pre_line=pre_line,
                                 inter_cell=inter_cell, post_line=post_line)

    def generate_row_bottom_border(self):
        """Generate a border which appears at the bottom of rows"""
        pre_line = '╟' + self.padding * '─'

        inter_cell = self.padding * '─'
        if self.column_borders:
            inter_cell += '┼'
        inter_cell += self.padding * '─'

        post_line = self.padding * '─' + '╢'

        return self.generate_row(row_data=self.empty_data, fill_char='─', pre_line=pre_line,
                                 inter_cell=inter_cell, post_line=post_line)

    def generate_table_bottom_border(self):
        """Generate a border which appears at the bottom of the table"""
        pre_line = '╚' + self.padding * '═'

        inter_cell = self.padding * '═'
        if self.column_borders:
            inter_cell += '╧'
        inter_cell += self.padding * '═'

        post_line = self.padding * '═' + '╝'

        return self.generate_row(row_data=self.empty_data, fill_char='═', pre_line=pre_line,
                                 inter_cell=inter_cell, post_line=post_line)

    def generate_header(self) -> str:
        """Generate table header"""
        pre_line = '║' + self.padding * SPACE

        inter_cell = self.padding * SPACE
        if self.column_borders:
            inter_cell += '│'
        inter_cell += self.padding * SPACE

        post_line = self.padding * SPACE + '║'

        # Create the bordered header
        header_buf = io.StringIO()
        header_buf.write(self.generate_table_top_border())
        header_buf.write('\n')
        header_buf.write(self.generate_row(pre_line=pre_line, inter_cell=inter_cell, post_line=post_line))
        header_buf.write('\n')
        header_buf.write(self.generate_header_bottom_border())

        return header_buf.getvalue()

    def generate_data_row(self, row_data: Sequence[Any]) -> str:
        """
        Generate a data row

        :param row_data: data with an entry for each column in the row
        :return: data row string
        """
        pre_line = '║' + self.padding * SPACE

        inter_cell = self.padding * SPACE
        if self.column_borders:
            inter_cell += '│'
        inter_cell += self.padding * SPACE

        post_line = self.padding * SPACE + '║'

        return self.generate_row(row_data=row_data, pre_line=pre_line, inter_cell=inter_cell, post_line=post_line)

    def generate_table(self, table_data: Sequence[Sequence[Any]], *, include_header: bool = True) -> str:
        """
        Generate a table from a data set

        :param table_data: Data with an entry for each data row of the table. Each entry should have data for
                           each column in the row.
        :param include_header: If True, then a header will be included at top of table. (Defaults to True)
        """
        table_buf = io.StringIO()

        if include_header:
            header = self.generate_header()
            table_buf.write(header)
        else:
            top_border = self.generate_table_top_border()
            table_buf.write(top_border)

        table_buf.write('\n')

        for index, row_data in enumerate(table_data):
            if index > 0:
                row_bottom_border = self.generate_row_bottom_border()
                table_buf.write(row_bottom_border)
                table_buf.write('\n')

            row = self.generate_data_row(row_data)
            table_buf.write(row)
            table_buf.write('\n')

        table_buf.write(self.generate_table_bottom_border())
        return table_buf.getvalue()


class AlternatingTable(BorderedTable):
    """
    Implementation of BorderedTable which uses background colors to distinguish between rows instead of row border lines.
    This class can be used to create the whole table at once or one row at a time.
    """
    def __init__(self, cols: Sequence[Column], *, tab_width: int = 4, column_borders: bool = True, padding: int = 1,
                 bg_odd: Optional[ansi.bg] = None, bg_even: Optional[ansi.bg] = ansi.bg.bright_black) -> None:
        """
        AlternatingTable initializer

        :param cols: column definitions for this table
        :param tab_width: all tabs will be replaced with this many spaces. If a row's fill_char is a tab,
                          then it will be converted to one space.
        :param column_borders: if True, borders between columns will be included. This gives the table a grid-like
                               appearance. Turning off column borders results in a unified appearance between
                               a row's cells. (Defaults to True)
        :param padding: number of spaces between text and left/right borders of cell
        :param bg_odd: optional background color for odd numbered rows (defaults to None)
        :param bg_even: optional background color for even numbered rows (defaults to gray)
        :raises: ValueError if padding is less than 0
        """
        super().__init__(cols, tab_width=tab_width, column_borders=column_borders, padding=padding)
        self.row_num = 1
        self.bg_odd = None if bg_odd is None else functools.partial(ansi.style, bg=bg_odd)
        self.bg_even = None if bg_even is None else functools.partial(ansi.style, bg=bg_even)

    def _apply_bg_color(self, data: Any) -> str:
        """
        Convert data to text and apply background color to it based on what row is being generated

        :param data: data being colored
        :return: converted data
        """
        if self.row_num % 2 == 0 and self.bg_even is not None:
            return self.bg_even(data)
        elif self.row_num % 2 != 0 and self.bg_odd is not None:
            return self.bg_odd(data)
        else:
            return str(data)

    def generate_data_row(self, row_data: Sequence[Any]) -> str:
        """
        Generate a data row

        :param row_data: data with an entry for each column in the row
        :return: data row string
        """
        pre_line = '║' + self.padding * SPACE

        inter_cell = self.padding * SPACE
        if self.column_borders:
            inter_cell += '│'
        inter_cell += self.padding * SPACE

        post_line = self.padding * SPACE + '║'

        fill_char = self._apply_bg_color(SPACE)
        pre_line = self._apply_bg_color(pre_line)
        inter_cell = self._apply_bg_color(inter_cell)
        post_line = self._apply_bg_color(post_line)

        # Apply appropriate background color to data, but don't change the original
        to_display = [self._apply_bg_color(col) for col in row_data]

        row = self.generate_row(row_data=to_display, fill_char=fill_char, pre_line=pre_line,
                                inter_cell=inter_cell, post_line=post_line)
        self.row_num += 1
        return row

    def generate_table(self, table_data: Sequence[Sequence[Any]], *, include_header: bool = True) -> str:
        """
        Generate a table from a data set

        :param table_data: Data with an entry for each data row of the table. Each entry should have data for
                           each column in the row.
        :param include_header: If True, then a header will be included at top of table. (Defaults to True)
        """
        table_buf = io.StringIO()

        if include_header:
            header = self.generate_header()
            table_buf.write(header)
        else:
            top_border = self.generate_table_top_border()
            table_buf.write(top_border)

        table_buf.write('\n')

        for row_data in table_data:
            row = self.generate_data_row(row_data)
            table_buf.write(row)
            table_buf.write('\n')

        table_buf.write(self.generate_table_bottom_border())
        return table_buf.getvalue()
