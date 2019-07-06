Help
====

use the categorize() function to create help categories

Use ``help_method()`` to custom roll your own help messages.

See :ref:`features/argument_processing:Help Messages`

Grouping Commands
-----------------

By default, the ``help`` command displays::

  Documented commands (type help <topic>):
  ========================================
  alias  help     ipy    py    run_pyscript  set    shortcuts
  edit   history  macro  quit  run_script    shell

If you have a large number of commands, you can optionally group your commands
into categories. Here's the output from the example ``help_categories.py``::

  Documented commands (type help <topic>):

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
    py                  Invoke python command, shell, or script
    quit                Exits this application
    run_pyscript        Runs a python script file inside the console
    run_script          Runs commands in script file that is encoded as either ASCII or UTF-8 text
    set                 usage: set [-h] [-a] [-l] [settable [settable ...]]
    shell               Execute a command as if at the OS prompt
    shortcuts           Lists shortcuts available
    unalias             Unsets aliases
    version             Version command

