Integrating with the OS
=======================

- how to redirect output
- executing OS commands from within ``cmd2``
- editors
- paging
- exit codes
- Automation and calling cmd2 from other CLI/CLU tools via commands at
  invocation and quit


Invoking With Arguments
-----------------------

Typically you would invoke a ``cmd2`` program by typing::

    $ python mycmd2program.py

or::

    $ mycmd2program.py

Either of these methods will launch your program and enter the ``cmd2`` command
loop, which allows the user to enter commands, which are then executed by your
program.

You may want to execute commands in your program without prompting the user for
any input. There are several ways you might accomplish this task. The easiest
one is to pipe commands and their arguments into your program via standard
input. You don't need to do anything to your program in order to use this
technique. Here's a demonstration using the ``examples/example.py`` included in
the source code of ``cmd2``::

    $ echo "speak -p some words" | python examples/example.py
    omesay ordsway

Using this same approach you could create a text file containing the commands
you would like to run, one command per line in the file. Say your file was
called ``somecmds.txt``. To run the commands in the text file using your
``cmd2`` program (from a Windows command prompt)::

    c:\cmd2> type somecmds.txt | python.exe examples/example.py
    omesay ordsway

By default, ``cmd2`` programs also look for commands pass as arguments from the
operating system shell, and execute those commands before entering the command
loop::

    $ python examples/example.py help

    Documented commands (type help <topic>):
    ========================================
    alias  help     macro   orate  quit          run_script  set    shortcuts
    edit   history  mumble  py     run_pyscript  say         shell  speak

    (Cmd)

You may need more control over command line arguments passed from the operating
system shell. For example, you might have a command inside your ``cmd2``
program which itself accepts arguments, and maybe even option strings. Say you
wanted to run the ``speak`` command from the operating system shell, but have
it say it in pig latin::

    $ python example/example.py speak -p hello there
    python example.py speak -p hello there
    usage: speak [-h] [-p] [-s] [-r REPEAT] words [words ...]
    speak: error: the following arguments are required: words
    *** Unknown syntax: -p
    *** Unknown syntax: hello
    *** Unknown syntax: there
    (Cmd)

Uh-oh, that's not what we wanted. ``cmd2`` treated ``-p``, ``hello``, and
``there`` as commands, which don't exist in that program, thus the syntax
errors.

There is an easy way around this, which is demonstrated in
``examples/cmd_as_argument.py``. By setting ``allow_cli_args=False`` you can so
your own argument parsing of the command line::

    $ python examples/cmd_as_argument.py speak -p hello there
    ellohay heretay

Check the source code of this example, especially the ``main()`` function, to
see the technique.
