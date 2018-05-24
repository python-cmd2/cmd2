#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How to display tabular data within a cmd2 application
    2) How to display output using a pager

NOTE: IF the table does not entirely fit within the screen of your terminal, then it will be displayed using a pager.
You can use the arrow keys (left, right, up, and down) to scroll around the table as well as the PageUp/PageDown keys.
You can quit out of the pager by typing "q".  You can also search for text within the pager using "/".

WARNING: This example requires the tabulate module.
"""
import functools

import cmd2
import tabulate

# Format to use with tabulate module when displaying tables
TABLE_FORMAT = 'grid'

# Create a function to format a fixed-width table for pretty-printing using the desired table format
table = functools.partial(tabulate.tabulate, tablefmt=TABLE_FORMAT)

# Population data from Wikipedia: https://en.wikipedia.org/wiki/List_of_cities_proper_by_population
EXAMPLE_DATA = [['Shanghai', 'Shanghai', 'China', 'Asia', 24183300, 6340.5, 3814],
                ['Beijing', 'Hebei', 'China', 'Asia', 20794000, 1749.57, 11885],
                ['Karachi', 'Sindh', 'Pakistan', 'Asia', 14910352, 615.58, 224221],
                ['Shenzen', 'Guangdong', 'China', 'Asia', 13723000, 1493.32, 9190],
                ['Guangzho', 'Guangdong', 'China', 'Asia', 13081000, 1347.81, 9705],
                ['Mumbai', ' Maharashtra', 'India', 'Asia', 12442373, 465.78, 27223],
                ['Istanbul', 'Istanbul', 'Turkey', 'Eurasia', 12661000, 620.29, 20411],
                ]
EXAMPLE_HEADERS = ['City', 'Province', 'Country', 'Continent', 'Population', 'Area (km^2)', 'Pop. Density (/km^2)']


class TableDisplay(cmd2.Cmd):
    """Example cmd2 application showing how you can display tabular data."""

    def __init__(self):
        super().__init__()

    def ptable(self, tabular_data, headers=()):
        """Format tabular data for pretty-printing as a fixed-width table and then display it using a pager.

        :param tabular_data: required argument - can be a list-of-lists (or another iterable of iterables), a list of
                             named tuples, a dictionary of iterables, an iterable of dictionaries, a two-dimensional
                             NumPy array, NumPy record array, or a Pandas dataframe.
        :param headers: (optional) - to print nice column headers, supply this argument:
                        - headers can be an explicit list of column headers
                        - if `headers="firstrow"`, then the first row of data is used
                        - if `headers="keys"`, then dictionary keys or column indices are used
                        - Otherwise, a headerless table is produced
        """
        formatted_table = table(tabular_data, headers=headers)
        self.ppaged(formatted_table)

    def do_table(self, _):
        """Display data on the Earth's most populated cities in a table."""
        self.ptable(tabular_data=EXAMPLE_DATA, headers=EXAMPLE_HEADERS)


if __name__ == '__main__':
    app = TableDisplay()
    app.cmdloop()
