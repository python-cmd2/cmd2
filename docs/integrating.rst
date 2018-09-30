.. cmd2 documentation for integration with other tools

Integrating cmd2 with external tools
====================================


Integrating cmd2 with the shell
-------------------------------

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
    alias  help     load    orate  pyscript  say  shell      speak
    edit   history  mumble  py     quit      set  shortcuts  unalias

    (Cmd)

You may need more control over command line arguments passed from the operating
system shell. For example, you might have a command inside your ``cmd2`` program
which itself accepts arguments, and maybe even option strings. Say you wanted to
run the ``speak`` command from the operating system shell, but have it say it in
pig latin::

    $ python example/example.py speak -p hello there
    python example.py speak -p hello there
    usage: speak [-h] [-p] [-s] [-r REPEAT] words [words ...]
    speak: error: the following arguments are required: words
    *** Unknown syntax: -p
    *** Unknown syntax: hello
    *** Unknown syntax: there
    (Cmd)

Uh-oh, that's not what we wanted. ``cmd2`` treated ``-p``, ``hello``, and
``there`` as commands, which don't exist in that program, thus the syntax errors.

There is an easy way around this, which is demonstrated in
``examples/cmd_as_argument.py``. By setting ``allow_cli_args=False`` you can so
your own argument parsing of the command line::

    $ python examples/cmd_as_argument.py speak -p hello there
    ellohay heretay

Check the source code of this example, especially the ``main()`` function, to
see the technique.


Integrating cmd2 with event loops
---------------------------------

Throughout this documentation we have focused on the **90%** use case, that is
the use case we believe around **90+%** of our user base is looking for.  This
focuses on ease of use and the best out-of-the-box experience where developers
get the most functionality for the least amount of effort.  We are talking about
running cmd2 applications with the ``cmdloop()`` method::

    from cmd2 import Cmd
    class App(Cmd):
        # customized attributes and methods here
    app = App()
    app.cmdloop()

However, there are some limitations to this way of using ``cmd2``, mainly that
``cmd2`` owns the inner loop of a program.  This can be unnecessarily
restrictive and can prevent using libraries which depend on controlling their
own event loop.

Many Python concurrency libraries involve or require an event loop which they
are in control of such as asyncio_, gevent_, Twisted_, etc.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _gevent: http://www.gevent.org/
.. _Twisted: https://twistedmatrix.com

``cmd2`` applications can be executed in a fashion where ``cmd2`` doesn't own
the main loop for the program by using code like the following::

    import cmd2

    class Cmd2EventBased(cmd2.Cmd):
        def __init__(self):
            cmd2.Cmd.__init__(self)

        # ... your class code here ...

    if __name__ == '__main__':
        app = Cmd2EventBased()
        app.preloop()

        # Do this within whatever event loop mechanism you wish to run a single command
        cmd_line_text = "help history"
        app.runcmds_plus_hooks([cmd_line_text])

        app.postloop()

The **runcmds_plus_hooks()** method is a convenience method to run multiple
commands via **onecmd_plus_hooks()**.  It properly deals with ``load`` commands
which under the hood put commands in a FIFO queue as it reads them in from a
script file.

The **onecmd_plus_hooks()** method will do the following to execute a single
``cmd2`` command in a normal fashion:

#. Parse user input into `Statement` object
#. Call methods registered with `register_postparsing_hook()`
#. Redirect output, if user asked for it and it's allowed
#. Start timer
#. Call methods registered with `register_precmd_hook()`
#. Call `precmd()` - for backwards compatibility with ``cmd.Cmd``
#. Add statement to history
#. Call `do_command` method
#. Call methods registered with `register_postcmd_hook()`
#. Call `postcmd(stop, statement)` - for backwards compatibility with ``cmd.Cmd``
#. Stop timer and display the elapsed time
#. Stop redirecting output if it was redirected
#. Call methods registered with `register_cmdfinalization_hook()`

Running in this fashion enables the ability to integrate with an external event
loop.  However, how to integrate with any specific event loop is beyond the
scope of this documentation.  Please note that running in this fashion comes
with several disadvantages, including:

* Requires the developer to write more code
* Does not support transcript testing
* Does not allow commands at invocation via command-line arguments

Here is a little more info on ``runcmds_plus_hooks``:

.. automethod:: cmd2.cmd2.Cmd.runcmds_plus_hooks
