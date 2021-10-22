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


class Book:
    """Class used for example data"""

    def __init__(self, title: str, due_date: str) -> None:
        self.title = title
        self.due_date = due_date


class Person:
    """Class used for example data"""

    def __init__(self, name: str, birthday: str, department: str) -> None:
        self.name = name
        self.birthday = birthday
        self.department = department
        self.books: List[Book] = []


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
    Demonstrates how to nest tables using the override_data_style keyword to handle tables with conflicting styles.
    In these cases, the inner tables reset the background color applied by the outer AlternatingTable.

    It also demonstrates coloring various aspects of tables.
    """

    # Create data for this example
    person_data: List[Person] = []
    person_1 = Person("Bill Anderson", "01/22/1955", "Accounting")
    person_1.books.append(Book("Great Expectations", "11/01/2025"))
    person_1.books.append(Book("Strange Case of Dr Jekyll and Mr Hyde", "07/16/2026"))
    person_1.books.append(Book("Dune", "01/24/2027"))

    person_2 = Person("Arthur Smith", "06/11/1974", "Automotive")
    person_2.books.append(Book("Nineteen Eighty-Four", "08/07/2025"))
    person_2.books.append(Book("Pride and Prejudice", "04/13/2026"))
    person_2.books.append(Book("Fahrenheit 451", "07/29/2026"))
    person_2.books.append(Book("The Count of Monte Cristo", "10/15/2027"))

    person_data.append(person_1)
    person_data.append(person_2)

    # Define table which presents Person data fields vertically with no header.
    # This will be nested in the parent table.
    person_columns: List[Column] = list()
    person_columns.append(Column("", width=10))
    person_columns.append(Column("", width=20))

    # The text labels in this table will be bold text. They will also be aligned by the table code.
    # When styled text is aligned, a TextStyle.RESET_ALL sequence is inserted between the aligned text
    # and the fill characters. Therefore, the Person table will contain TextStyle.RESET_ALL sequences,
    # which would interfere with the background color applied by the parent table. To account for this,
    # we will color the Person tables to match the background colors of the parent AlternatingTable's rows
    # and set override_data_style to False in the Person column. See below for that.
    odd_person_tbl = SimpleTable(person_columns, data_bg=EightBitBg.GRAY_0)
    even_person_tbl = SimpleTable(person_columns, data_bg=EightBitBg.GRAY_15)

    # Define AlternatingTable table for books checked out by people in the first table.
    # This will also be nested in the parent table.
    books_columns: List[Column] = list()
    books_columns.append(Column("Title", width=28))
    books_columns.append(Column("Due Date", width=10))

    books_tbl = AlternatingTable(
        books_columns,
        column_borders=False,
        border_fg=EightBitFg.GRAY_15,
        header_bg=EightBitBg.GRAY_0,
        odd_bg=EightBitBg.GRAY_0,
        even_bg=EightBitBg.GRAY_15,
    )

    # Define parent AlternatingTable which contains Person and Book tables
    parent_tbl_columns: List[Column] = list()

    # Both the Person and Books tables already have background colors. Set override_data_style
    # to False so the parent AlternatingTable does not apply background color to them.
    parent_tbl_columns.append(Column("Person", width=odd_person_tbl.total_width(), override_data_style=False))
    parent_tbl_columns.append(Column("Books", width=books_tbl.total_width(), override_data_style=False))

    parent_tbl = AlternatingTable(
        parent_tbl_columns,
        column_borders=False,
        header_bg=EightBitBg.GRAY_0,
        odd_bg=EightBitBg.GRAY_0,
        even_bg=EightBitBg.GRAY_15,
    )

    # Construct the tables
    parent_table_data: List[List[Any]] = []
    for row, person in enumerate(person_data, start=1):
        # First build the person table and color it based on row number
        person_tbl = even_person_tbl if row % 2 == 0 else odd_person_tbl

        # This table has three rows and two columns
        table_data = [
            [ansi.style("Name", bold=True), person.name],
            [ansi.style("Birthday", bold=True), person.birthday],
            [ansi.style("Department", bold=True), person.department],
        ]

        # Build the person table string
        person_tbl_str = person_tbl.generate_table(table_data, include_header=False, row_spacing=0)

        # Now build this person's book table
        table_data = [[book.title, book.due_date] for book in person.books]
        book_tbl_str = books_tbl.generate_table(table_data)

        # Add these tables to the parent table's data
        parent_table_data.append(['\n' + person_tbl_str, '\n' + book_tbl_str + '\n\n'])

    # Build the parent table
    top_table_str = parent_tbl.generate_table(parent_table_data)
    ansi_print(top_table_str)


if __name__ == '__main__':
    # Default to terminal mode so redirecting to a file won't include the ANSI style sequences
    ansi.allow_style = ansi.AllowStyle.TERMINAL
    basic_tables()
    nested_tables()
