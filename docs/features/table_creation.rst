Table Creation
==============

``cmd2`` provides a table creation class called
:attr:`cmd2.table_creator.TableCreator`. This class handles ANSI style
sequences and characters with display widths greater than 1 when performing
width calculations. It was designed with the ability to build tables one row at
a time. This helps when you have large data sets that you don't want to hold
in memory or when you receive portions of the data set incrementally.

``TableCreator`` has one public method:
:attr:`cmd2.table_creator.TableCreator.generate_row()`

This function and the :attr:`cmd2.table_creator.Column`
class provide all features needed to build tables with headers, borders,
colors, horizontal and vertical alignment, and wrapped text. However, it's
generally easier to inherit from this class and implement a more granular API
rather than use ``TableCreator`` directly.

The following table classes build upon ``TableCreator`` and are provided in
the :ref:`api/table_creator:cmd2.table_creator` module. They can be used as is
or as examples for how to build your own table classes.

:attr:`cmd2.table_creator.SimpleTable` - Implementation of TableCreator which
generates a borderless table with an optional divider row after the header.
This class can be used to create the whole table at once or one row at a time.

:attr:`cmd2.table_creator.BorderedTable` - Implementation of TableCreator which
generates a table with borders around the table and between rows. Borders
between columns can also be toggled. This class can be used to create the whole
table at once or one row at a time.

:attr:`cmd2.table_creator.AlternatingTable` - Implementation of BorderedTable
which uses background colors to distinguish between rows instead of row border
lines. This class can be used to create the whole table at once or one row at a
time.

See the table_creation_ example to see these classes in use

.. _table_creation: https://github.com/python-cmd2/cmd2/blob/master/examples/table_creation.py
