=========================================
Features requiring only parameter changes
=========================================

Several aspects of a ``cmd2`` application's behavior
can be controlled simply by setting attributes of ``App``.

(To define your own user-settable parameters, see :ref:`parameters`)

Case-insensitivity
==================

By default, all ``cmd2`` command names are case-insensitive; 
``sing the blues`` and ``SiNg the blues`` are equivalent.  To change this, 
set ``App.case_insensitive`` to False.

Whether or not you set ``case_insensitive``, *please do not* define
command method names with any uppercase letters.  ``cmd2`` will probably
do something evil if you do.

Multiline commands
==================

Like cmd_, ``cmd2`` assumes that a line break ends any command.
However, ``App.multilineCommands`` is a list of commands that are assumed to span
multiple lines.  For these commands 

``cmd2.Cmd.multilineCommands`` defaults to [], so you may set your own list
of multiline command names (without ``do_``)::

    class App(Cmd):
        multilineCommands = ['lenghtycommand']
        def do_lengthycommand(self, args):
            # ...          

Shortcuts
=========

Special-character shortcuts for common commands can make life more convenient for your
users.  Shortcuts are used without a space separating them from their arguments,
like ``!ls``.  By default, the following shortcuts are defined:

  ``?``
    help
    
  ``!`` 
    shell: run as OS-level command
    
  ``@``
    load script file
    
  ``@@``
    load script file; filename is relative to current script location
    
To define more shortcuts, update the dict ``App.shortcuts`` with the
{'shortcut': 'command_name'} (omit ``do_``)::

  class App(Cmd2):
      Cmd2.shortcuts.update({'*': 'sneeze', '~': 'squirm'})

Timing
======

Setting ``App.timing`` to ``True`` outputs timing data after
every application command is executed.  |settable|

Debug
=====

Setting ``App.debug`` to ``True`` will produce detailed error stacks
whenever the application generates an error.  |settable|

.. |settable| replace:: The user can ``set`` this parameter
                        during application execution.  
                        (See :ref:`parameters`)

.. _quiet:

Quiet
=====

Controls whether ``self.pfeedback('message')`` output is suppressed;
useful for non-essential feedback that the user may not always want
to read.  Only relevant if :ref:`outputters` are used.

Settability
===========

If you wish the user to be able to set one of these
application-controlling attributes while the application 
is running, add its name to ``App.settable``.  See
:ref:`parameters`.

Abbreviated commands
====================
