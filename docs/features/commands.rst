Commands
========

.. _cmd: https://docs.python.org/3/library/cmd.html

How to create a command with a ``do_command`` method,

Parsed statements
-----------------

``cmd2`` passes ``arg`` to a ``do_`` method (or ``default``) as a Statement, a
subclass of string that includes many attributes of the parsed input:

command
    Name of the command called

args
    The arguments to the command with output redirection
    or piping to shell commands removed

command_and_args
    A string of just the command and the arguments, with
    output redirection or piping to shell commands removed

argv
    A list of arguments a-la ``sys.argv``, including
    the command as ``argv[0]`` and the subsequent
    arguments as additional items in the list.
    Quotes around arguments will be stripped as will
    any output redirection or piping portions of the command

raw
    Full input exactly as typed.

terminator
    Character used to end a multiline command



If ``Statement`` does not contain an attribute, querying for it will return
``None``.

(Getting ``arg`` as a ``Statement`` is technically "free", in that it requires
no application changes from the cmd_ standard, but there will be no result
unless you change your application to *use* any of the additional attributes.)


