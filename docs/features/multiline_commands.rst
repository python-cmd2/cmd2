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

Continuation prompt
-------------------

When a user types a :ref:`Multiline Command
<features/multiline_commands:Multiline Commands>` it may span more than one
line of input. The prompt for the first line of input is specified by the
:attr:`cmd2.Cmd.prompt` instance attribute - see
:ref:`features/prompt:Customizing the Prompt`. The prompt for subsequent lines
of input is defined by the :attr:`cmd2.Cmd.continuation_prompt` attribute.

Use cases
---------
Multiline commands should probably be used sparingly in order to preserve a
good user experience for your ``cmd2``-based line-oriented command interpreter
application.

However, some use cases benefit significantly from the ability to have commands
that span more than one line. For example, you might want the ability for your
user to type in a SQL command, which can often span lines and which are
terminated with a semicolon.

We estimate that less than 5 percent of ``cmd2`` applications use this feature.
But it is here for those uses cases where it provides value.
