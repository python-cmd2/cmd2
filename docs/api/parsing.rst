cmd2.parsing
===============

.. autoclass:: cmd2.Statement
    :members:

    .. attribute:: command

      The name of the command after shortcuts and macros have been expanded

    .. attribute:: multiline_command

      If the command is a multi-line command, the name of the command will be
      in this attribute. Otherwise, it will be an empty string.

    .. attribute:: args

      The arguments to the command as a string with spaces between the words,
      excluding output redirection and command terminators. If the user used
      quotes in their input, they remain here, and you will have to handle them
      on your own.

    .. attribute:: arg_list

      The arguments to the command as a list, excluding output
      redirection and command terminators. Each argument is represented as an
      element in the list. Quoted arguments remain quoted. If you want to
      remove the quotes, use :func:`cmd2.utils.strip_quotes` or use
      ``argv[1:]``

    .. attribute:: raw

      If you want full access to exactly what the user typed at the input
      prompt you can get it, but you'll have to parse it on your own,
      including:

        - shortcuts and aliases
        - quoted commands and arguments
        - output redirection
        - multi-line command terminator handling

      If you use multiline commands, all the input will be passed to you in
      this string, but there will be embedded newlines where the user hit
      return to continue the command on the next line.


.. autoclass:: cmd2.parsing.StatementParser
    :members:

    .. automethod:: __init__
