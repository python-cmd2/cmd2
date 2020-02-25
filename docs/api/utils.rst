cmd2.utils
==========


Settings
--------

.. autoclass:: cmd2.utils.Settable
    :members:

    .. automethod:: __init__


Quote Handling
--------------

.. autofunction:: cmd2.utils.is_quoted

.. autofunction:: cmd2.utils.quote_string

.. autofunction:: cmd2.utils.quote_string_if_needed

.. autofunction:: cmd2.utils.strip_quotes


IO Handling
-----------

.. autoclass:: cmd2.utils.StdSim
    :members:

.. autoclass:: cmd2.utils.ByteBuf
    :members:

.. autoclass:: cmd2.utils.ProcReader
    :members:


Tab Completion
--------------

.. autoclass:: cmd2.utils.CompletionError
    :members:

.. autofunction:: cmd2.utils.basic_complete


Text Alignment
--------------

.. autoclass:: cmd2.utils.TextAlignment
    :members:

.. autofunction:: cmd2.utils.align_text

.. autofunction:: cmd2.utils.align_left

.. autofunction:: cmd2.utils.align_right

.. autofunction:: cmd2.utils.align_center

.. autofunction:: cmd2.utils.truncate_line


Miscellaneous
-------------

.. autofunction:: cmd2.utils.str_to_bool

.. autofunction:: cmd2.utils.namedtuple_with_defaults

.. autofunction:: cmd2.utils.categorize

.. autofunction:: cmd2.utils.remove_duplicates

.. autofunction:: cmd2.utils.alphabetical_sort

.. autofunction:: cmd2.utils.natural_sort
