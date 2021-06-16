Argument Processing
===================

``cmd2`` makes it easy to add sophisticated argument processing to your
commands using the `argparse
<https://docs.python.org/3/library/argparse.html>`_ python module. ``cmd2``
handles the following for you:

1. Parsing input and quoted strings like the Unix shell

2. Parse the resulting argument list using an instance of
   ``argparse.ArgumentParser`` that you provide

3. Passes the resulting ``argparse.Namespace`` object to your command function.
   The ``Namespace`` includes the ``Statement`` object that was created when
   parsing the command line. It can be retrieved by calling
   ``cmd2_statement.get()`` on the ``Namespace``.

4. Adds the usage message from the argument parser to your command.

5. Checks if the ``-h/--help`` option is present, and if so, display the help
   message for the command

These features are all provided by the ``@with_argparser`` decorator which is
importable from ``cmd2``.

See the either the argprint_ or decorator_ example to learn more about how to
use the various ``cmd2`` argument processing decorators in your ``cmd2``
applications.

.. _argprint: https://github.com/python-cmd2/cmd2/blob/master/examples/arg_print.py
.. _decorator: https://github.com/python-cmd2/cmd2/blob/master/examples/decorator_example.py

``cmd2`` provides the following decorators for assisting with parsing arguments
passed to commands:

* :func:`cmd2.decorators.with_argparser`
* :func:`cmd2.decorators.with_argument_list`

All of these decorators accept an optional **preserve_quotes** argument which
defaults to ``False``. Setting this argument to ``True`` is useful for cases
where you are passing the arguments to another command which might have its own
argument parsing.


Argument Parsing
----------------

For each command in the ``cmd2`` subclass which requires argument parsing,
create a unique instance of ``argparse.ArgumentParser()`` which can parse the
input appropriately for the command. Then decorate the command method with the
``@with_argparser`` decorator, passing the argument parser as the first
parameter to the decorator. This changes the second argument to the command
method, which will contain the results of ``ArgumentParser.parse_args()``.

Here's what it looks like::

      from cmd2 import Cmd2ArgumentParser, with_argparser

      argparser = Cmd2ArgumentParser()
      argparser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
      argparser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
      argparser.add_argument('-r', '--repeat', type=int, help='output [n] times')
      argparser.add_argument('word', nargs='?', help='word to say')

      @with_argparser(argparser)
      def do_speak(self, opts)
         """Repeats what you tell me to."""
         arg = opts.word
         if opts.piglatin:
            arg = '%s%say' % (arg[1:], arg[0])
         if opts.shout:
            arg = arg.upper()
         repetitions = opts.repeat or 1
         for i in range(min(repetitions, self.maxrepeats)):
            self.poutput(arg)

.. warning::

    It is important that each command which uses the ``@with_argparser``
    decorator be passed a unique instance of a parser.  This limitation is due
    to bugs in CPython prior to Python 3.7 which make it impossible to make a
    deep copy of an instance of a ``argparse.ArgumentParser``.

    See the table_display_ example for a work-around that demonstrates how to
    create a function which returns a unique instance of the parser you want.


.. note::

   The ``@with_argparser`` decorator sets the ``prog`` variable in the argument
   parser based on the name of the method it is decorating. This will override
   anything you specify in ``prog`` variable when creating the argument parser.

.. _table_display: https://github.com/python-cmd2/cmd2/blob/master/examples/table_display.py


Help Messages
-------------

By default, ``cmd2`` uses the docstring of the command method when a user asks
for help on the command. When you use the ``@with_argparser`` decorator, the
docstring for the ``do_*`` method is used to set the description for the
``argparse.ArgumentParser``.

With this code::

   from cmd2 import Cmd2ArgumentParser, with_argparser

   argparser = Cmd2ArgumentParser()
   argparser.add_argument('tag', help='tag')
   argparser.add_argument('content', nargs='+', help='content to surround with tag')
   @with_argparser(argparser)
   def do_tag(self, args):
      """create a html tag"""
      self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
      self.stdout.write('\n')

the ``help tag`` command displays:

.. code-block:: text

   usage: tag [-h] tag content [content ...]

   create a html tag

   positional arguments:
     tag         tag
     content     content to surround with tag

   optional arguments:
     -h, --help  show this help message and exit


If you would prefer you can set the ``description`` while instantiating the
``argparse.ArgumentParser`` and leave the docstring on your method empty::

   from cmd2 import Cmd2ArgumentParser, with_argparser

   argparser = Cmd2ArgumentParser(description='create an html tag')
   argparser.add_argument('tag', help='tag')
   argparser.add_argument('content', nargs='+', help='content to surround with tag')
   @with_argparser(argparser)
   def do_tag(self, args):
      self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
      self.stdout.write('\n')

Now when the user enters ``help tag`` they see:

.. code-block:: text

   usage: tag [-h] tag content [content ...]

   create an html tag

   positional arguments:
     tag         tag
     content     content to surround with tag

   optional arguments:
     -h, --help  show this help message and exit


To add additional text to the end of the generated help message, use the ``epilog`` variable::

   from cmd2 import Cmd2ArgumentParser, with_argparser

   argparser = Cmd2ArgumentParser(description='create an html tag',
                                  epilog='This command cannot generate tags with no content, like <br/>.')
   argparser.add_argument('tag', help='tag')
   argparser.add_argument('content', nargs='+', help='content to surround with tag')
   @with_argparser(argparser)
   def do_tag(self, args):
      self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
      self.stdout.write('\n')

Which yields:

.. code-block:: text

   usage: tag [-h] tag content [content ...]

   create an html tag

   positional arguments:
     tag         tag
     content     content to surround with tag

   optional arguments:
     -h, --help  show this help message and exit

   This command cannot generate tags with no content, like <br/>

.. warning::

    If a command **foo** is decorated with one of cmd2's argparse decorators,
    then **help_foo** will not be invoked when ``help foo`` is called.  The
    argparse_ module provides a rich API which can be used to tweak every
    aspect of the displayed help and we encourage ``cmd2`` developers to
    utilize that.

.. _argparse: https://docs.python.org/3/library/argparse.html


Argument List
-------------

The default behavior of ``cmd2`` is to pass the user input directly to your
``do_*`` methods as a string. The object passed to your method is actually a
``Statement`` object, which has additional attributes that may be helpful,
including ``arg_list`` and ``argv``::

    class CmdLineApp(cmd2.Cmd):
        """ Example cmd2 application. """

        def do_say(self, statement):
            # statement contains a string
            self.poutput(statement)

        def do_speak(self, statement):
            # statement also has a list of arguments
            # quoted arguments remain quoted
            for arg in statement.arg_list:
                self.poutput(arg)

        def do_articulate(self, statement):
            # statement.argv contains the command
            # and the arguments, which have had quotes
            # stripped
            for arg in statement.argv:
                self.poutput(arg)


If you don't want to access the additional attributes on the string passed to
you``do_*`` method you can still have ``cmd2`` apply shell parsing rules to the
user input and pass you a list of arguments instead of a string. Apply the
``@with_argument_list`` decorator to those methods that should receive an
argument list instead of a string::

    from cmd2 import with_argument_list

    class CmdLineApp(cmd2.Cmd):
        """ Example cmd2 application. """

        def do_say(self, cmdline):
            # cmdline contains a string
            pass

        @with_argument_list
        def do_speak(self, arglist):
            # arglist contains a list of arguments
            pass


Unknown Positional Arguments
----------------------------

If you want all unknown arguments to be passed to your command as a list of
strings, then decorate the command method with the
``@with_argparser(..., with_unknown_args=True)`` decorator.

Here's what it looks like::

    from cmd2 import Cmd2ArgumentParser, with_argparser

    dir_parser = Cmd2ArgumentParser()
    dir_parser.add_argument('-l', '--long', action='store_true', help="display in long format with one item per line")

    @with_argparser(dir_parser, with_unknown_args=True)
    def do_dir(self, args, unknown):
        """List contents of current directory."""
        # No arguments for this command
        if unknown:
            self.perror("dir does not take any positional arguments:")
            self.do_help('dir')
            self.last_result = CommandResult('', 'Bad arguments')
            return

        # Get the contents as a list
        contents = os.listdir(self.cwd)

        ...

Using A Custom Namespace
------------------------

In some cases, it may be necessary to write custom ``argparse`` code that is
dependent on state data of your application.  To support this ability while
still allowing use of the decorators, ``@with_argparser`` has an optional
argument called ``ns_provider``.

``ns_provider`` is a Callable that accepts a ``cmd2.Cmd`` object as an argument
and returns an ``argparse.Namespace``::

    Callable[[cmd2.Cmd], argparse.Namespace]

For example::

    def settings_ns_provider(self) -> argparse.Namespace:
        """Populate an argparse Namespace with current settings"""
        ns = argparse.Namespace()
        ns.app_settings = self.settings
        return ns

To use this function with the argparse decorators, do the following::

    @with_argparser(my_parser, ns_provider=settings_ns_provider)

The Namespace is passed by the decorators to the ``argparse`` parsing functions
which gives your custom code access to the state data it needs for its parsing
logic.

Subcommands
------------

Subcommands are supported for commands using the ``@with_argparser`` decorator.
The syntax is based on argparse sub-parsers.

You may add multiple layers of subcommands for your command. ``cmd2`` will
automatically traverse and tab complete subcommands for all commands using
argparse.

See the subcommands_ example to learn more about how to
use subcommands in your ``cmd2`` application.

.. _subcommands: https://github.com/python-cmd2/cmd2/blob/master/examples/subcommands.py


Argparse Extensions
-------------------

``cmd2`` augments the standard ``argparse.nargs`` with range tuple capability:

- ``nargs=(5,)`` - accept 5 or more items
- ``nargs=(8, 12)`` - accept 8 to 12 items

``cmd2`` also provides the :class:`cmd2.argparse_custom.Cmd2ArgumentParser`
class which inherits from ``argparse.ArgumentParser`` and improves error and
help output.


Decorator Order
---------------

If you are using custom decorators in combination with
``@cmd2.with_argparser``, then the
order of your custom decorator(s) relative to the ``cmd2`` decorator matters
when it comes to runtime behavior and ``argparse`` errors.  There is nothing
``cmd2``-specific here, this is just a side-effect of how decorators work in
Python.  To learn more about how decorators work, see decorator_primer_.

If you want your custom decorator's runtime behavior to occur in the case of
an ``argparse`` error, then that decorator needs to go **after** the
``argparse`` one, e.g.::

    @cmd2.with_argparser(foo_parser)
    @my_decorator
    def do_foo(self, args: argparse.Namespace) -> None:
        """foo docs"""
        pass

However, if you do NOT want the custom decorator runtime behavior to occur
even in the case of an `argparse` error, then that decorator needs to go
**before** the ``arpgarse`` one, e.g.::

    @my_decorator
    @cmd2.with_argparser(bar_parser)
    def do_bar(self, args: argparse.Namespace) -> None:
        """bar docs"""
        pass

The help_categories_ example demonstrates both above cases in a concrete
fashion.

.. _decorator_primer: https://realpython.com/primer-on-python-decorators
.. _help_categories: https://github.com/python-cmd2/cmd2/blob/master/examples/help_categories.py


Reserved Argument Names
-----------------------
``cmd2`` argparse decorators add the following attributes to argparse
Namespaces. To avoid naming collisions, do not use any of the names for your
argparse arguments.

- ``cmd2_statement`` - ``cmd2.Cmd2AttributeWrapper`` object containing
  ``cmd2.Statement`` object that was created when parsing the command line.
- ``cmd2_handler`` - ``cmd2.Cmd2AttributeWrapper`` object containing
  a subcommand handler function or ``None`` if one was not set.
- ``__subcmd_handler__`` - used by cmd2 to identify the handler for a
  subcommand created with ``@cmd2.as_subcommand_to`` decorator.
