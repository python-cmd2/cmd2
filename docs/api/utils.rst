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

.. autofunction:: cmd2.utils.quote_specific_tokens

.. autofunction:: cmd2.utils.unquote_specific_tokens


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

.. autoclass:: cmd2.utils.CompletionMode

    .. attribute:: NONE

        Tab completion will be disabled during read_input() call. Use of custom
        up-arrow history supported.

    .. attribute:: COMMANDS

        read_input() will tab complete cmd2 commands and their arguments.
        cmd2's command line history will be used for up arrow if history is not
        provided. Otherwise use of custom up-arrow history supported.

    .. attribute:: CUSTOM

        read_input() will tab complete based on one of its following parameters
        (choices, choices_provider, completer, parser). Use of custom up-arrow
        history supported

.. autoclass:: cmd2.utils.CustomCompletionSettings

    .. automethod:: __init__


Text Alignment
--------------

.. autoclass:: cmd2.utils.TextAlignment
    :members:
    :undoc-members:

.. autofunction:: cmd2.utils.align_text

.. autofunction:: cmd2.utils.align_left

.. autofunction:: cmd2.utils.align_right

.. autofunction:: cmd2.utils.align_center

.. autofunction:: cmd2.utils.truncate_line


Miscellaneous
-------------

.. autofunction:: cmd2.utils.str_to_bool

.. autofunction:: cmd2.utils.categorize

.. autofunction:: cmd2.utils.remove_duplicates

.. autofunction:: cmd2.utils.alphabetical_sort

.. autofunction:: cmd2.utils.natural_sort
