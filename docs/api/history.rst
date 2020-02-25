cmd2.history
===============

Classes for storing the history of previously entered commands.


.. autoclass:: cmd2.history.History
    :members:


.. autoclass:: cmd2.history.HistoryItem
    :members:

    .. attribute:: statement

      The :class:`~cmd2.Statement` object parsed from user input

    .. attribute:: idx

      The 1-based index of this statement in the history list
