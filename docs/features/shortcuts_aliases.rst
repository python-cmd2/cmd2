Shortcuts and Aliases
=====================

Shortcuts
---------

Command shortcuts for long command names and common commands can make life more
convenient for your users. Shortcuts are used without a space separating them
from their arguments, like ``!ls``.  By default, the following shortcuts are
defined:

  ``?``
    help

  ``!``
    shell: run as OS-level command

  ``@``
    run script file

  ``@@``
    run script file; filename is relative to current script location

To define more shortcuts, update the dict ``App.shortcuts`` with the
{'shortcut': 'command_name'} (omit ``do_``)::

  class App(Cmd):
      def __init__(self):
        shortcuts = dict(cmd2.DEFAULT_SHORTCUTS)
        shortcuts.update({'*': 'sneeze', '~': 'squirm'})
        cmd2.Cmd.__init__(self, shortcuts=shortcuts)

.. warning::

  Shortcuts need to be created by updating the ``shortcuts`` dictionary
  attribute prior to calling the ``cmd2.Cmd`` super class ``__init__()``
  method.  Moreover, that super class init method needs to be called after
  updating the ``shortcuts`` attribute  This warning applies in general to many
  other attributes which are not settable at runtime.

Note: Command and alias names cannot start with a shortcut

Aliases
-------

In addition to shortcuts, ``cmd2`` provides a full alias feature via the
``alias`` command. Aliases work in a similar fashion to aliases in the Bash
shell.

The syntax to create an alias is: ``alias create name command [args]``.

  Ex: ``alias create ls !ls -lF``

Redirectors and pipes should be quoted in alias definition to prevent the
``alias create`` command from being redirected::

    alias create save_results print_results ">" out.txt

Tab completion recognizes an alias, and completes as if its actual value
was on the command line.

For more details run: ``help alias create``

Use ``alias list`` to see all or some of your aliases. The output of this
command displays your aliases using the same command that was used to create
them. Therefore you can place this output in a ``cmd2`` startup script to
recreate your aliases each time you start the application

  Ex: ``alias list``

For more details run: ``help alias list``

Use ``alias delete`` to remove aliases

For more details run: ``help alias delete``

Note: Aliases cannot have the same name as a command
