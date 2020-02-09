Help
====

From our experience, end users rarely read documentation no matter how high-
quality or useful that documentation might be.  So it is important that you
provide good built-in help within your application.  Fortunately, ``cmd2``
makes this easy.

Getting Help
------------

``cmd2`` makes it easy for end users of ``cmd2`` applications to get help via
the built-in ``help`` command.  The ``help`` command by itself displays a list
of the commands available:

.. code-block:: text

    (Cmd) help

    Documented commands (use 'help -v' for verbose/'help <topic>' for details):
    ===========================================================================
    alias  help     ipy    py    run_pyscript  set    shortcuts
    edit   history  macro  quit  run_script    shell

The ``help`` command can also be used to provide detailed help for a specific
command:

.. code-block:: text

    (Cmd) help quit
    Usage: quit [-h]

    Exit this application

    optional arguments:
      -h, --help  show this help message and exit

Providing Help
--------------

``cmd2`` makes it easy for developers of ``cmd2`` applications to provide this
help.  By default, the help for a command is the docstring for the ``do_*``
method defining the command - e.g. for a command **foo**, that command is
implementd by defining the ``do_foo`` method and the docstring for that method
is the help.

For commands which use one of the ``argparse`` decorators to parse arguments,
help is provided by ``argparse``. See
:ref:`features/argument_processing:Help Messages` for more information.

Occasionally there might be an unusual circumstance where providing static help
text isn't good enough and you want to provide dynamic information in the help
text for a command.  To meet this need, if a ``help_foo`` method is defined to
match the ``do_foo`` method, then that method will be used to provide the help
for command **foo**.  This dynamic help is only supported for commands which
do not use an ``argparse`` decorator because didn't want different output for
``help cmd`` than for ``cmd -h``.

Categorizing Commands
---------------------

By default, the ``help`` command displays::

  Documented commands (use 'help -v' for verbose/'help <topic>' for details):
  ===========================================================================
  alias  help     ipy    py    run_pyscript  set    shortcuts
  edit   history  macro  quit  run_script    shell

If you have a large number of commands, you can optionally group your commands
into categories. Here's the output from the example ``help_categories.py``::

  Documented commands (use 'help -v' for verbose/'help <topic>' for details):

  Application Management
  ======================
  deploy  findleakers  redeploy  sessions  stop
  expire  list         restart   start     undeploy

  Command Management
  ==================
  disable_commands  enable_commands

  Connecting
  ==========
  connect  which

  Server Information
  ==================
  resources  serverinfo  sslconnectorciphers  status  thread_dump  vminfo

  Other
  =====
  alias   edit  history  py    run_pyscript  set    shortcuts
  config  help  macro    quit  run_script    shell  version

There are 2 methods of specifying command categories, using the
``@with_category`` decorator or with the ``categorize()`` function. Once a
single command category is detected, the help output switches to a categorized
mode of display. All commands with an explicit category defined default to the
category `Other`.

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

The ``help`` command also has a verbose option (``help -v`` or ``help
--verbose``) that combines the help categories with per-command Help Messages::

    Documented commands (use 'help -v' for verbose/'help <topic>' for details):

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
    alias               Manage aliases
    config              Config command
    edit                Run a text editor and optionally open a file with it
    help                List available commands or provide detailed help for a specific command
    history             View, run, edit, save, or clear previously entered commands
    macro               Manage macros
    py                  Invoke Python command or shell
    quit                Exits this application
    run_pyscript        Runs a python script file inside the console
    run_script          Runs commands in script file that is encoded as either ASCII or UTF-8 text
    set                 Set a settable parameter or show current settings of parameters
    shell               Execute a command as if at the OS prompt
    shortcuts           List available shortcuts
    version             Version command

When called with the ``-v`` flag for verbose help, the one-line description for
each command is provided by the first line of the docstring for that command's
associated ``do_*`` method.
