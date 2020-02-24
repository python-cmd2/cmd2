cmd2.plugin
===========

.. autoclass:: cmd2.plugin.PostparsingData
    :members:

    .. attribute:: stop

      Request the command loop terminate by setting ``True``

    .. attribute:: statement

      The :class:`~cmd2.Statement` object parsed from user input


.. autoclass:: cmd2.plugin.PrecommandData
    :members:

    .. attribute:: statement

      The :class:`~cmd2.Statement` object parsed from user input


.. autoclass:: cmd2.plugin.PostcommandData
    :members:

    .. attribute:: stop

      Request the command loop terminate by setting ``True``

    .. attribute:: statement

      The :class:`~cmd2.Statement` object parsed from user input


.. autoclass:: cmd2.plugin.CommandFinalizationData
    :members:

    .. attribute:: stop

      Request the command loop terminate by setting ``True``

    .. attribute:: statement

      The :class:`~cmd2.Statement` object parsed from user input
