# Table Creation

As of version 3.0.0, `cmd2` no longer includes custom code for table creation.

This is because `cmd2` now has a dependency on [rich](https://github.com/Textualize/rich) which has
excellent support for this feature.

Please see rich's documentation on [Tables](https://rich.readthedocs.io/en/latest/tables.html) for
more information.

The [rich_tables.py](https://github.com/python-cmd2/cmd2/blob/main/examples/rich_tables.py) example
demonstrates how to use `rich` tables in a `cmd2` application.
