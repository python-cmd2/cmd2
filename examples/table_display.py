#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating the following:
    1) How to display tabular data
    2) How to display output using a pager

NOTE: IF the table does not entirely fit within the screen of your terminal, then it will be displayed using a pager.
You can use the arrow keys (left, right, up, and down) to scroll around the table as well as the PageUp/PageDown keys.
You can quit out of the pager by typing "q".  You can also search for text within the pager using "/".

WARNING: This example requires the tableformatter module: https://github.com/python-tableformatter/tableformatter
- pip install tableformatter
"""
import functools

import cmd2
import tableformatter as tf

try:
    from colored import bg
    BACK_PRI = bg(4)
    BACK_ALT = bg(2)
except ImportError:
    try:
        from colorama import Back
        BACK_PRI = Back.LIGHTBLUE_EX
        BACK_ALT = Back.LIGHTYELLOW_EX
    except ImportError:
        BACK_PRI = ''
        BACK_ALT = ''

# Format to use for the grid style when displaying tables with the tableformatter module
grid_style = tf.AlternatingRowGrid(BACK_PRI, BACK_ALT)  # Use rows of alternating color to assist as a visual guide

# Create a function to format a fixed-width table for pretty-printing using the desired table format
table = functools.partial(tf.generate_table, grid_style=grid_style)


# Formatter functions

def no_dec(num: float) -> str:
    """Format a floating point number with no decimal places."""
    return "{}".format(round(num))


def two_dec(num: float) -> str:
    """Format a floating point number with 2 decimal places."""
    return "{0:.2f}".format(num)


# Population data from Wikipedia: https://en.wikipedia.org/wiki/List_of_cities_proper_by_population


# ############ Table data formatted as an iterable of iterable fields ############

EXAMPLE_ITERABLE_DATA = [['Shanghai', 'Shanghai', 'China', 'Asia', 24183300, 6340.5],
                         ['Beijing', 'Hebei', 'China', 'Asia', 20794000, 1749.57],
                         ['Karachi', 'Sindh', 'Pakistan', 'Asia', 14910352, 615.58],
                         ['Shenzen', 'Guangdong', 'China', 'Asia', 13723000, 1493.32],
                         ['Guangzho', 'Guangdong', 'China', 'Asia', 13081000, 1347.81],
                         ['Mumbai', 'Maharashtra', 'India', 'Asia', 12442373, 465.78],
                         ['Istanbul', 'Istanbul', 'Turkey', 'Eurasia', 12661000, 620.29],
                         ]

# Calculate population density
for row in EXAMPLE_ITERABLE_DATA:
    row.append(row[-2]/row[-1])


# # Column headers plus optional formatting info for each column
columns = [tf.Column('City', header_halign=tf.ColumnAlignment.AlignCenter),
           tf.Column('Province', header_halign=tf.ColumnAlignment.AlignCenter),
           'Country',   # NOTE: If you don't need any special effects, you can just pass a string
           tf.Column('Continent', cell_halign=tf.ColumnAlignment.AlignCenter),
           tf.Column('Population', cell_halign=tf.ColumnAlignment.AlignRight, formatter=tf.FormatCommas()),
           tf.Column('Area (km²)', width=7, header_halign=tf.ColumnAlignment.AlignCenter,
                     cell_halign=tf.ColumnAlignment.AlignRight, formatter=two_dec),
           tf.Column('Pop. Density (/km²)', width=12, header_halign=tf.ColumnAlignment.AlignCenter,
                     cell_halign=tf.ColumnAlignment.AlignRight, formatter=no_dec),
           ]


# ######## Table data formatted as an iterable of python objects #########

class CityInfo(object):
    """City information container"""
    def __init__(self, city: str, province: str, country: str, continent: str, population: int, area: float):
        self.city = city
        self.province = province
        self.country = country
        self.continent = continent
        self._population = population
        self._area = area

    def get_population(self):
        """Population of the city"""
        return self._population

    def get_area(self):
        """Area of city in km²"""
        return self._area


def pop_density(data: CityInfo):
    """Calculate the population density from the data entry"""
    if isinstance(data, CityInfo):
        return no_dec(data.get_population() / data.get_area())

    return ''


EXAMPLE_OBJECT_DATA = [CityInfo('Shanghai', 'Shanghai', 'China', 'Asia', 24183300, 6340.5),
                       CityInfo('Beijing', 'Hebei', 'China', 'Asia', 20794000, 1749.57),
                       CityInfo('Karachi', 'Sindh', 'Pakistan', 'Asia', 14910352, 615.58),
                       CityInfo('Shenzen', 'Guangdong', 'China', 'Asia', 13723000, 1493.32),
                       CityInfo('Guangzho', 'Guangdong', 'China', 'Asia', 13081000, 1347.81),
                       CityInfo('Mumbai', 'Maharashtra', 'India', 'Asia', 12442373, 465.78),
                       CityInfo('Istanbul', 'Istanbul', 'Turkey', 'Eurasia', 12661000, 620.29),
                       ]

# If table entries are python objects, all columns must be defined with the object attribute to query for each field
#   - attributes can be fields or functions. If a function is provided, the formatter will automatically call
#     the function to retrieve the value
obj_cols = [tf.Column('City', attrib='city', header_halign=tf.ColumnAlignment.AlignCenter),
            tf.Column('Province', attrib='province', header_halign=tf.ColumnAlignment.AlignCenter),
            tf.Column('Country', attrib='country'),
            tf.Column('Continent', attrib='continent', cell_halign=tf.ColumnAlignment.AlignCenter),
            tf.Column('Population', attrib='get_population', cell_halign=tf.ColumnAlignment.AlignRight,
                      formatter=tf.FormatCommas()),
            tf.Column('Area (km²)', attrib='get_area', width=7, header_halign=tf.ColumnAlignment.AlignCenter,
                      cell_halign=tf.ColumnAlignment.AlignRight, formatter=two_dec),
            tf.Column('Pop. Density (/km²)', width=12, header_halign=tf.ColumnAlignment.AlignCenter,
                      cell_halign=tf.ColumnAlignment.AlignRight, obj_formatter=pop_density),
            ]

# TODO: Color row text foreground based on population density


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
        formatted_table = table(rows=tabular_data, columns=headers)
        self.ppaged(formatted_table, chop=True)

    def do_table(self, _):
        """Display data on the Earth's most populated cities in a table."""
        self.ptable(EXAMPLE_ITERABLE_DATA, columns)

    def do_object_table(self, _):
        """Display data on the Earth's most populated cities in a table."""
        self.ptable(EXAMPLE_OBJECT_DATA, obj_cols)


if __name__ == '__main__':
    app = TableDisplay()
    app.debug = True
    app.cmdloop()
