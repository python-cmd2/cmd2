.. _decorators:

===================
Argument Processing
===================

``cmd2`` makes it easy to add sophisticated argument processing to your commands using the ``argparse`` python module.
``cmd2`` handles the following for you:

1. Parsing input and quoted strings like the Unix shell
2. Parse the resulting argument list using an instance of ``argparse.ArgumentParser`` that you provide
3. Passes the resulting ``argparse.Namespace`` object to your command function
4. Adds the usage message from the argument parser to your command.
5. Checks if the ``-h/--help`` option is present, and if so, display the help message for the command

These features are all provided by the ``@with_argparser`` decorator which is importable from ``cmd2``.

See the either the argprint_ or decorator_ example to learn more about how to use the various ``cmd2`` argument
processing decorators in your ``cmd2`` applications.

.. _argprint: https://github.com/python-cmd2/cmd2/blob/master/examples/arg_print.py
.. _decorator: https://github.com/python-cmd2/cmd2/blob/master/examples/decorator_example.py


Decorators provided by cmd2 for argument processing
===================================================
``cmd2`` provides the following decorators for assisting with parsing arguments passed to commands:

.. automethod:: cmd2.cmd2.with_argument_list
.. automethod:: cmd2.cmd2.with_argparser
.. automethod:: cmd2.cmd2.with_argparser_and_unknown_args

All of these decorators accept an optional **preserve_quotes** argument which defaults to ``False``.
Setting this argument to ``True`` is useful for cases where you are passing the arguments to another
command which might have its own argument parsing.


Using the argument parser decorator
===================================

For each command in the ``cmd2`` subclass which requires argument parsing,
create a unique instance of ``argparse.ArgumentParser()`` which can parse the
input appropriately for the command. Then decorate the command method with
the ``@with_argparser`` decorator, passing the argument parser as the
first parameter to the decorator. This changes the second argument to the command method, which will contain the results
of ``ArgumentParser.parse_args()``.

Here's what it looks like::

      import argparse
      from cmd2 import with_argparser

      argparser = argparse.ArgumentParser()
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

    It is important that each command which uses the ``@with_argparser`` decorator be passed a unique instance of a
    parser.  This limitation is due to bugs in CPython prior to Python 3.7 which make it impossible to make a deep copy
    of an instance of a ``argparse.ArgumentParser``.

    See the table_display_ example for a work-around that demonstrates how to create a function which returns a unique
    instance of the parser you want.


.. note::

   The ``@with_argparser`` decorator sets the ``prog`` variable in
   the argument parser based on the name of the method it is decorating.
   This will override anything you specify in ``prog`` variable when
   creating the argument parser.

.. _table_display: https://github.com/python-cmd2/cmd2/blob/master/examples/table_display.py


Help Messages
=============

By default, cmd2 uses the docstring of the command method when a user asks
for help on the command. When you use the ``@with_argparser``
decorator, the docstring for the ``do_*`` method is used to set the description for the ``argparse.ArgumentParser`` is
With this code::

   import argparse
   from cmd2 import with_argparser

   argparser = argparse.ArgumentParser()
   argparser.add_argument('tag', help='tag')
   argparser.add_argument('content', nargs='+', help='content to surround with tag')
   @with_argparser(argparser)
   def do_tag(self, args):
      """create a html tag"""
      self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
      self.stdout.write('\n')

The ``help tag`` command displays:

.. code-block:: none

   usage: tag [-h] tag content [content ...]

   create a html tag

   positional arguments:
     tag         tag
     content     content to surround with tag

   optional arguments:
     -h, --help  show this help message and exit


If you would prefer you can set the ``description`` while instantiating the ``argparse.ArgumentParser`` and leave the
docstring on your method empty::

   import argparse
   from cmd2 import with_argparser

   argparser = argparse.ArgumentParser(description='create an html tag')
   argparser.add_argument('tag', help='tag')
   argparser.add_argument('content', nargs='+', help='content to surround with tag')
   @with_argparser(argparser)
   def do_tag(self, args):
      self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
      self.stdout.write('\n')

Now when the user enters ``help tag`` they see:

.. code-block:: none

   usage: tag [-h] tag content [content ...]

   create an html tag

   positional arguments:
     tag         tag
     content     content to surround with tag

   optional arguments:
     -h, --help  show this help message and exit


To add additional text to the end of the generated help message, use the ``epilog`` variable::

   import argparse
   from cmd2 import with_argparser

   argparser = argparse.ArgumentParser(description='create an html tag',
                                       epilog='This command can not generate tags with no content, like <br/>.')
   argparser.add_argument('tag', help='tag')
   argparser.add_argument('content', nargs='+', help='content to surround with tag')
   @with_argparser(argparser)
   def do_tag(self, args):
      self.stdout.write('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))
      self.stdout.write('\n')

Which yields:

.. code-block:: none

   usage: tag [-h] tag content [content ...]

   create an html tag

   positional arguments:
     tag         tag
     content     content to surround with tag

   optional arguments:
     -h, --help  show this help message and exit

   This command can not generate tags with no content, like <br/>

.. warning::

    If a command **foo** is decorated with one of cmd2's argparse decorators, then **help_foo** will not
    be invoked when ``help foo`` is called.  The argparse_ module provides a rich API which can be used to
    tweak every aspect of the displayed help and we encourage ``cmd2`` developers to utilize that.

.. _argparse: https://docs.python.org/3/library/argparse.html


Grouping Commands
=================

By default, the ``help`` command displays::

  Documented commands (type help <topic>):
  ========================================
  alias    findleakers  pyscript    sessions             status       vminfo
  config   help         quit        set                  stop         which
  connect  history      redeploy    shell                thread_dump
  deploy   list         resources   shortcuts            unalias
  edit     load         restart     sslconnectorciphers  undeploy
  expire   py           serverinfo  start                version

If you have a large number of commands, you can optionally group your commands into categories.
Here's the output from the example ``help_categories.py``::

  Documented commands (type help <topic>):

  Application Management
  ======================
  deploy  findleakers  redeploy  sessions  stop
  expire  list         restart   start     undeploy

  Connecting
  ==========
  connect  which

  Server Information
  ==================
  resources  serverinfo  sslconnectorciphers  status  thread_dump  vminfo

  Other
  =====
  alias   edit  history  py        quit  shell      unalias
  config  help  load     pyscript  set   shortcuts  version


There are 2 methods of specifying command categories, using the ``@with_category`` decorator or with the
``categorize()`` function. Once a single command category is detected, the help output switches to a categorized
mode of display. All commands with an explicit category defined default to the category `Other`.

Using the ``@with_category`` decorator::

  @with_category(CMD_CAT_CONNECTING)
  def do_which(self, _):
      """Which command"""
      self.poutput('Which')

Using the ``categorize()`` function:

    You can call with a single function::

        def do_connect(self, _):
            """Connect command"""
            self.poutput('Connect')

        # Tag the above command functions under the category Connecting
        categorize(do_connect, CMD_CAT_CONNECTING)

    Or with an Iterable container of functions::

        def do_undeploy(self, _):
            """Undeploy command"""
            self.poutput('Undeploy')

        def do_stop(self, _):
            """Stop command"""
            self.poutput('Stop')

        def do_findleakers(self, _):
            """Find Leakers command"""
            self.poutput('Find Leakers')

        # Tag the above command functions under the category Application Management
        categorize((do_undeploy,
                    do_stop,
                    do_findleakers), CMD_CAT_APP_MGMT)

The ``help`` command also has a verbose option (``help -v`` or ``help --verbose``) that combines
the help categories with per-command Help Messages::

    Documented commands (type help <topic>):

    Application Management
    ================================================================================
    deploy              Deploy command
    expire              Expire command
    findleakers         Find Leakers command
    list                List command
    redeploy            Redeploy command
    restart             usage: restart [-h] {now,later,sometime,whenever}
    sessions            Sessions command
    start               Start command
    stop                Stop command
    undeploy            Undeploy command

    Connecting
    ================================================================================
    connect             Connect command
    which               Which command

    Server Information
    ================================================================================
    resources              Resources command
    serverinfo             Server Info command
    sslconnectorciphers    SSL Connector Ciphers command is an example of a command that contains
                           multiple lines of help information for the user. Each line of help in a
                           contiguous set of lines will be printed and aligned in the verbose output
                           provided with 'help --verbose'
    status                 Status command
    thread_dump            Thread Dump command
    vminfo                 VM Info command

    Other
    ================================================================================
    alias               Define or display aliases
    config              Config command
    edit                Edit a file in a text editor
    help                List available commands with "help" or detailed help with "help cmd"
    history             usage: history [-h] [-r | -e | -s | -o FILE | -t TRANSCRIPT] [arg]
    load                Runs commands in script file that is encoded as either ASCII or UTF-8 text
    py                  Invoke python command, shell, or script
    pyscript            Runs a python script file inside the console
    quit                Exits this application
    set                 usage: set [-h] [-a] [-l] [settable [settable ...]]
    shell               Execute a command as if at the OS prompt
    shortcuts           Lists shortcuts available
    unalias             Unsets aliases
    version             Version command


Receiving an argument list
==========================

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


Using the argument parser decorator and also receiving a a list of unknown positional arguments
===============================================================================================
If you want all unknown arguments to be passed to your command as a list of strings, then
decorate the command method with the ``@with_argparser_and_unknown_args`` decorator.

Here's what it looks like::

    import argparse
    from cmd2 import with_argparser_and_unknown_args

    dir_parser = argparse.ArgumentParser()
    dir_parser.add_argument('-l', '--long', action='store_true', help="display in long format with one item per line")

    @with_argparser_and_unknown_args(dir_parser)
    def do_dir(self, args, unknown):
        """List contents of current directory."""
        # No arguments for this command
        if unknown:
            self.perror("dir does not take any positional arguments:", traceback_war=False)
            self.do_help('dir')
            self._last_result = CommandResult('', 'Bad arguments')
            return

        # Get the contents as a list
        contents = os.listdir(self.cwd)

        ...

Sub-commands
============
Sub-commands are supported for commands using either the ``@with_argparser`` or
``@with_argparser_and_unknown_args`` decorator.  The syntax for supporting them is based on argparse sub-parsers.

You may add multiple layers of sub-commands for your command. Cmd2 will automatically traverse and tab-complete
sub-commands for all commands using argparse.

See the subcommands_ and tab_autocompletion_ example to learn more about how to use sub-commands in your ``cmd2`` application.

.. _subcommands: https://github.com/python-cmd2/cmd2/blob/master/examples/subcommands.py
.. _tab_autocompletion: https://github.com/python-cmd2/cmd2/blob/master/examples/tab_autocompletion.py
