#!/usr/bin/env python
# coding=utf-8
"""Examples of using the cmd2 table creation API"""

import functools
import sys
from typing import (
    Any,
    List,
)

from cmd2 import (
    EightBitBg,
    EightBitFg,
    Fg,
    ansi,
)
from cmd2.table_creator import (
    AlternatingTable,
    BorderedTable,
    Column,
    HorizontalAlignment,
    SimpleTable,
)

# Text styles used in the tables
bold_yellow = functools.partial(ansi.style, fg=Fg.LIGHT_YELLOW, bold=True)
blue = functools.partial(ansi.style, fg=Fg.LIGHT_BLUE)
green = functools.partial(ansi.style, fg=Fg.GREEN)


class DollarFormatter:
    """Example class to show that any object type can be passed as data to TableCreator and converted to a string"""

    def __init__(self, val: float) -> None:
        self.val = val

    def __str__(self) -> str:
        """Returns the value in dollar currency form (e.g. $100.22)"""
        return "${:,.2f}".format(self.val)


class Relative:
    """Class used for example data"""

    def __init__(self, name: str, relationship: str) -> None:
        self.name = name
        self.relationship = relationship


class Book:
    """Class used for example data"""

    def __init__(self, title: str, year_published: str) -> None:
        self.title = title
        self.year_published = year_published


class Author:
    """Class used for example data"""

    def __init__(self, name: str, birthday: str, place_of_birth: str) -> None:
        self.name = name
        self.birthday = birthday
        self.place_of_birth = place_of_birth
        self.books: List[Book] = []
        self.relatives: List[Relative] = []


def ansi_print(text):
    """Wraps style_aware_write so style can be stripped if needed"""
    ansi.style_aware_write(sys.stdout, text + '\n\n')


def basic_tables():
    """Demonstrates basic examples of the table classes"""

    # Table data which demonstrates handling of wrapping and text styles
    data_list: List[List[Any]] = list()
    data_list.append(["Billy Smith", "123 Sesame St.\n" "Fake Town, USA 33445", DollarFormatter(100333.03)])
    data_list.append(
        [
            "William Longfellow Marmaduke III",
            "984 Really Long Street Name Which Will Wrap Nicely\n" "Apt 22G\n" "Pensacola, FL 32501",
            DollarFormatter(55135.22),
        ]
    )
    data_list.append(
        [
            "James " + blue("Bluestone"),
            bold_yellow("This address has line feeds,\n" "text styles, and wrapping. ")
            + blue("Style is preserved across lines."),
            DollarFormatter(300876.10),
        ]
    )
    data_list.append(["John Jones", "9235 Highway 32\n" + green("Greenville") + ", SC 29604", DollarFormatter(82987.71)])

    # Table Columns (width does not account for any borders or padding which may be added)
    columns: List[Column] = list()
    columns.append(Column("Name", width=20))
    columns.append(Column("Address", width=38))
    columns.append(
        Column("Income", width=14, header_horiz_align=HorizontalAlignment.RIGHT, data_horiz_align=HorizontalAlignment.RIGHT)
    )

    st = SimpleTable(columns)
    table = st.generate_table(data_list)
    ansi_print(table)

    bt = BorderedTable(columns)
    table = bt.generate_table(data_list)
    ansi_print(table)

    at = AlternatingTable(columns)
    table = at.generate_table(data_list)
    ansi_print(table)


def nested_tables():
    """
    Demonstrates how to nest tables with styles which conflict with the parent table by setting style_data_text to False.
    It also demonstrates coloring various aspects of tables.
    """

    # Create data for this example
    author_data: List[Author] = []
    author_1 = Author("Frank Herbert", "10/08/1920", "Tacoma, Washington")
    author_1.books.append(Book("Dune", "1965"))
    author_1.books.append(Book("Dune Messiah", "1969"))
    author_1.books.append(Book("Children of Dune", "1976"))
    author_1.books.append(Book("God Emperor of Dune", "1981"))
    author_1.books.append(Book("Heretics of Dune", "1984"))
    author_1.books.append(Book("Chapterhouse: Dune", "1985"))
    author_1.relatives.append(Relative("Flora Lillian Parkinson", "First Wife"))
    author_1.relatives.append(Relative("Beverly Ann Stuart", "Second Wife"))
    author_1.relatives.append(Relative("Theresa Diane Shackelford", "Third Wife"))
    author_1.relatives.append(Relative("Penelope Herbert", "Daughter"))
    author_1.relatives.append(Relative("Brian Patrick Herbert", "Son"))
    author_1.relatives.append(Relative("Bruce Calvin Herbert", "Son"))

    author_2 = Author("Jane Austen", "12/16/1775", "Steventon, Hampshire, England")
    author_2.books.append(Book("Sense and Sensibility", "1811"))
    author_2.books.append(Book("Pride and Prejudice", "1813"))
    author_2.books.append(Book("Mansfield Park ", "1814"))
    author_2.books.append(Book("Emma", "1815"))
    author_2.books.append(Book("Northanger Abbey", "1818"))
    author_2.books.append(Book("Persuasion", "1818"))
    author_2.books.append(Book("Lady Susan", "1871"))
    author_2.relatives.append(Relative("James Austen", "Brother"))
    author_2.relatives.append(Relative("George Austen", "Brother"))
    author_2.relatives.append(Relative("Edward Austen", "Brother"))
    author_2.relatives.append(Relative("Henry Thomas Austen", "Brother"))
    author_2.relatives.append(Relative("Cassandra Elizabeth Austen", "Sister"))
    author_2.relatives.append(Relative("Francis William Austen", "Brother"))
    author_2.relatives.append(Relative("Charles John Austen", "Brother"))

    author_data.append(author_1)
    author_data.append(author_2)

    # Define table which presents Author data fields vertically with no header.
    # This will be nested in the parent table's first column.
    author_columns: List[Column] = list()
    author_columns.append(Column("", width=14))
    author_columns.append(Column("", width=20))

    # The text labels in this table will be bold text. They will also be aligned by the table code.
    # When styled text is aligned, a TextStyle.RESET_ALL sequence is inserted between the aligned text
    # and the fill characters. Therefore, the Author table will contain TextStyle.RESET_ALL sequences,
    # which would interfere with the background color applied by the parent table. To account for this,
    # we will manually color the Author tables to match the background colors of the parent AlternatingTable's
    # rows and set style_data_text to False in the Author column.
    odd_author_tbl = SimpleTable(author_columns, data_bg=EightBitBg.GRAY_0)
    even_author_tbl = SimpleTable(author_columns, data_bg=EightBitBg.GRAY_15)

    # Define AlternatingTable for books checked out by people in the first table.
    # This will be nested in the parent table's second column.
    books_columns: List[Column] = list()
    books_columns.append(Column(ansi.style("Title", bold=True), width=25))
    books_columns.append(
        Column(
            ansi.style("Published", bold=True),
            width=9,
            header_horiz_align=HorizontalAlignment.RIGHT,
            data_horiz_align=HorizontalAlignment.RIGHT,
        )
    )

    books_tbl = AlternatingTable(
        books_columns,
        column_borders=False,
        border_fg=EightBitFg.GRAY_15,
        header_bg=EightBitBg.GRAY_0,
        odd_bg=EightBitBg.GRAY_0,
        even_bg=EightBitBg.GRAY_15,
    )

    # Define BorderedTable for relatives of the author
    # This will be nested in the parent table's third column.
    relative_columns: List[Column] = list()
    relative_columns.append(Column(ansi.style("Name", bold=True), width=25))
    relative_columns.append(Column(ansi.style("Relationship", bold=True), width=12))

    # Since the header labels are bold, we have the same issue as the Author table. Therefore, we will manually
    # color Relatives tables to match the background colors of the parent AlternatingTable's rows and set style_data_text
    # to False in the Relatives column.
    odd_relatives_tbl = BorderedTable(
        relative_columns,
        border_fg=EightBitFg.GRAY_15,
        border_bg=EightBitBg.GRAY_0,
        header_bg=EightBitBg.GRAY_0,
        data_bg=EightBitBg.GRAY_0,
    )

    even_relatives_tbl = BorderedTable(
        relative_columns,
        border_fg=EightBitFg.GRAY_0,
        border_bg=EightBitBg.GRAY_15,
        header_bg=EightBitBg.GRAY_15,
        data_bg=EightBitBg.GRAY_15,
    )

    # Define parent AlternatingTable which contains Author and Book tables
    parent_tbl_columns: List[Column] = list()

    # All of the nested tables already have background colors. Set style_data_text
    # to False so the parent AlternatingTable does not apply background color to them.
    parent_tbl_columns.append(
        Column(ansi.style("Author", bold=True), width=odd_author_tbl.total_width(), style_data_text=False)
    )
    parent_tbl_columns.append(Column(ansi.style("Books", bold=True), width=books_tbl.total_width(), style_data_text=False))
    parent_tbl_columns.append(
        Column(ansi.style("Relatives", bold=True), width=odd_relatives_tbl.total_width(), style_data_text=False)
    )

    parent_tbl = AlternatingTable(
        parent_tbl_columns,
        column_borders=False,
        border_fg=EightBitFg.GRAY_93,
        header_bg=EightBitBg.GRAY_0,
        odd_bg=EightBitBg.GRAY_0,
        even_bg=EightBitBg.GRAY_15,
    )

    # Construct the tables
    parent_table_data: List[List[Any]] = []
    for row, author in enumerate(author_data, start=1):
        # First build the author table and color it based on row number
        author_tbl = even_author_tbl if row % 2 == 0 else odd_author_tbl

        # This table has three rows and two columns
        table_data = [
            [ansi.style("Name", bold=True), author.name],
            [ansi.style("Birthday", bold=True), author.birthday],
            [ansi.style("Place of Birth", bold=True), author.place_of_birth],
        ]

        # Build the author table string
        author_tbl_str = author_tbl.generate_table(table_data, include_header=False, row_spacing=0)

        # Now build this author's book table
        table_data = [[book.title, book.year_published] for book in author.books]
        book_tbl_str = books_tbl.generate_table(table_data)

        # Lastly build the relatives table and color it based on row number
        relatives_tbl = even_relatives_tbl if row % 2 == 0 else odd_relatives_tbl
        table_data = [[relative.name, relative.relationship] for relative in author.relatives]
        relatives_tbl_str = relatives_tbl.generate_table(table_data)

        # Add these tables to the parent table's data
        parent_table_data.append(['\n' + author_tbl_str, '\n' + book_tbl_str + '\n\n', '\n' + relatives_tbl_str + '\n\n'])

    # Build the parent table
    top_table_str = parent_tbl.generate_table(parent_table_data)
    ansi_print(top_table_str)


if __name__ == '__main__':
    # Default to terminal mode so redirecting to a file won't include the ANSI style sequences
    ansi.allow_style = ansi.AllowStyle.TERMINAL
    basic_tables()
    nested_tables()
