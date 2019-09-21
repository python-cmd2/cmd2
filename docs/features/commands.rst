Commands
========

.. _cmd: https://docs.python.org/3/library/cmd.html

``cmd2`` is designed to make it easy for you to create new commands. These
commmands form the backbone of your application. If you started writing your
application using cmd_, all the commands you have built will work when you move
to ``cmd2``. However, there are many more capabilities available in ``cmd2``
which you can take advantage of to add more robust features to your commands,
and which makes your commands easier to write. Before we get to all the good
stuff, let's briefly discuss how to create a new command in your application.


Basic Commands
--------------

The simplest ``cmd2`` application looks like this::

    #!/usr/bin/env python
    """A simple cmd2 application."""
    import cmd2


    class App(cmd2.Cmd):
        """A simple cmd2 application."""


    if __name__ == '__main__':
        import sys
        c = App()
        sys.exit(c.cmdloop())

This application subclasses ``cmd2.Cmd`` but has no code of it's own, so all
functionality (and there's quite a bit) is inherited. Lets create a simple
command in this application called ``echo`` which outputs any arguments given
to it. Add this method to the class::

    def do_echo(self, line):
        self.poutput(line)

When you type input into the ``cmd2`` prompt, the first space delimited word is
treated as the command name. ``cmd2`` looks for a method called
``do_commandname``. If it exists, it calls the method, passing the rest of the
user input as the first argument. If it doesn't exist ``cmd2`` prints an error
message. As a result of this behavior, the only thing you have to do to create
a new command is to define a new method in the class with the appropriate name.
This is exactly how you would create a command using the cmd_ module which is
part of the python standard library.

.. note::

   See :ref:`features/generating_output:Generating Output` if you are
   unfamiliar with the ``poutput()`` method.


Statements
----------

A command is passed one argument: a string which contains all the rest of the
user input. However, in ``cmd2`` this string is actually a ``Statement``
object, which is a subclass of ``str`` to retain backwards compatibility.

``cmd2`` has a much more sophsticated parsing engine than what's included in
the cmd_ module. This parsing handles:

- quoted arguments
- output redirection and piping
- multi-line commands
- shortcut, macro, and alias expansion

In addition to parsing all of these elements from the user input, ``cmd2`` also
has code to make all of these items work; it's almost transparent to you and to
the commands you write in your own application. However, by passing your
command the ``Statement`` object instead of just a plain string, you can get
visibility into what ``cmd2`` has done with the user input before your command
got it. You can also avoid writing a bunch of parsing code, because ``cmd2``
gives you access to what it has already parsed.

A ``Statement`` object is a subclass of ``str`` that contains the following
attributes:

command
    Name of the command called. You already know this because of the method
    ``cmd2`` called, but it can sometimes be nice to have it in a string, i.e.
    if you want your error messages to contain the command name.

args
    A string containing the arguments to the command with output redirection or
    piping to shell commands removed. It turns out that the "string" value of
    the ``Statement`` object has all the output redirection and piping clauses
    removed as well. Quotes remain in the string.

command_and_args
    A string of just the command and the arguments, with output redirection or
    piping to shell commands removed.

argv
    A list of arguments a-la ``sys.argv``, including the command as ``argv[0]``
    and the subsequent arguments as additional items in the list. Quotes around
    arguments will be stripped as will any output redirection or piping
    portions of the command.

raw
    Full input exactly as typed by the user.

terminator
    Character used to end a multiline command. You can configure multiple
    termination characters, and this attribute will tell you which one the user
    typed.

For many simple commands, like the ``echo`` command above, you can ignore the
``Statement`` object and all of it's attributes and just use the passed value
as a string. You might choose to use the ``argv`` attribute to do more
sophisticated argument processing. Before you go too far down that path, you
should check out the :ref:`features/argument_processing:Argument Processing`
functionality included with ``cmd2``.


Return Values
-------------

Most commands should return nothing (either by omitting a ``return`` statement,
or by ``return None``. This indicates that your command is finished (with or
without errors), and that ``cmd2`` should prompt the user for more input.

If you return ``True`` from a command method, that indicates to ``cmd2`` that
it should stop prompting for user input and cleanly exit. ``cmd2`` already
includes a ``quit`` command, but if you wanted to make another one called
``finis`` you could::

    def do_finis(self, line):
        """Exit the application"""
        return True


Exit Codes
----------

``cmd2`` has basic infrastructure to support sh/ksh/csh/bash type exit codes.
The ``cmd2.Cmd`` object sets an ``exit_code`` attribute to zero when it is
instantiated. The value of this attribute is returned from the ``cmdloop()``
call. Therefore, if you don't do anything with this attribute in your code,
``cmdloop()`` will (almost) always return zero. There are a few built-in
``cmd2`` commands which set ``exit_code`` to ``-1`` if an error occurs.

You can use this capability to easily return your own values to the operating
system shell::

    #!/usr/bin/env python
    """A simple cmd2 application."""
    import cmd2


    class App(cmd2.Cmd):
        """A simple cmd2 application."""

    def do_bail(self, line):
        """Exit the application""
        self.perror("fatal error, exiting")
        self.exit_code = 2
        return true

    if __name__ == '__main__':
        import sys
        c = App()
        sys.exit(c.cmdloop())

If the app was run from the `bash` operating system shell, then you would see
the following interaction::

    (Cmd) bail
    fatal error, exiting
    $ echo $?
    2


Exception Handling
------------------

You may choose to catch and handle any exceptions which occur in
a command method. If the command method raises an exception, ``cmd2`` will
catch it and display it for you. The `debug` :ref:`setting
<features/settings:Settings>` controls how the exception is displayed. If
`debug` is `false`, which is the default, ``cmd2`` will display the exception
name and message. If `debug` is `true`, ``cmd2`` will display a traceback, and
then display the exception name and message.


Disabling or Hiding Commands
----------------------------

See :ref:`features/disable_commands:Disabling Commands` for details of how
to:

- remove commands included in ``cmd2``
- hide commands from the help menu
- disable and re-enable commands at runtime
