Multiline Commands
==================

Command input may span multiple lines for the commands whose names are listed
in the ``multiline_commands`` argument to ``cmd2.Cmd.__init__()``.  These
commands will be executed only after the user has entered a *terminator*. By
default, the command terminator is ``;``; specifying the ``terminators``
optional argument to ``cmd2.Cmd.__init__()`` allows different terminators.  A
blank line is *always* considered a command terminator (cannot be overridden).

In multiline commands, output redirection characters like ``>`` and ``|`` are
part of the command arguments unless they appear after the terminator.
