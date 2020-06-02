#!/usr/bin/env python
# coding=utf-8
"""Examples of using the cmd2 table creation API"""
import functools
import sys
from typing import Any, List

from cmd2 import ansi
from cmd2.table_creator import AlternatingTable, BorderedTable, Column, HorizontalAlignment, SimpleTable


class DollarFormatter:
    """Example class to show that any object type can be passed as data to TableCreator and converted to a string"""
    def __init__(self, val: float) -> None:
        self.val = val

    def __str__(self) -> str:
        """Returns the value in dollar currency form (e.g. $100.22)"""
        return "${:,.2f}".format(self.val)


# Text styles used in the data
bold_yellow = functools.partial(ansi.style, fg=ansi.fg.bright_yellow, bold=True)
blue = functools.partial(ansi.style, fg=ansi.fg.bright_blue)
green = functools.partial(ansi.style, fg=ansi.fg.green)

# Table Columns (width does not account for any borders or padding which may be added)
columns: List[Column] = list()
columns.append(Column("Name", width=20))
columns.append(Column("Address", width=38))
columns.append(Column("Income", width=14,
                      header_horiz_align=HorizontalAlignment.RIGHT,
                      data_horiz_align=HorizontalAlignment.RIGHT))

# Table data which demonstrates handling of wrapping and text styles
data_list: List[List[Any]] = list()
data_list.append(["Billy Smith",
                  "123 Sesame St.\n"
                  "Fake Town, USA 33445", DollarFormatter(100333.03)])
data_list.append(["William Longfellow Marmaduke III",
                  "984 Really Long Street Name Which Will Wrap Nicely\n"
                  "Apt 22G\n"
                  "Pensacola, FL 32501", DollarFormatter(55135.22)])
data_list.append(["James " + blue("Bluestone"),
                  bold_yellow("This address has line feeds,\n"
                              "text styles, and wrapping. ") + blue("Style is preserved across lines."),
                  DollarFormatter(300876.10)])
data_list.append(["John Jones",
                  "9235 Highway 32\n"
                  + green("Greenville") + ", SC 29604",
                  DollarFormatter(82987.71)])


def ansi_print(text):
    """Wraps style_aware_write so style can be stripped if needed"""
    ansi.style_aware_write(sys.stdout, text + '\n\n')


def main():
    # Default to terminal mode so redirecting to a file won't include the ANSI style sequences
    ansi.allow_style = ansi.STYLE_TERMINAL

    st = SimpleTable(columns)
    table = st.generate_table(data_list)
    ansi_print(table)

    bt = BorderedTable(columns)
    table = bt.generate_table(data_list)
    ansi_print(table)

    at = AlternatingTable(columns)
    table = at.generate_table(data_list)
    ansi_print(table)


if __name__ == '__main__':
    main()
