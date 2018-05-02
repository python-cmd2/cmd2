=========================================
Features requiring only parameter changes
=========================================

Several aspects of a ``cmd2`` application's behavior
can be controlled simply by setting attributes of ``App``.
A parameter can also be changed at runtime by the user *if*
its name is included in the dictionary ``app.settable``.
(To define your own user-settable parameters, see :ref:`parameters`)


Shortcuts
=========

Command shortcuts for long command names and common commands can make life more convenient for your users.
Shortcuts are used without a space separating them from their arguments, like ``!ls``.  By default, the
following shortcuts are defined:

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
      def __init__(self):
        # Make sure you update the shortcuts attribute before calling the super class __init__
        self.shortcuts.update({'*': 'sneeze', '~': 'squirm'})

        # Make sure to call this super class __init__ after updating shortcuts
        cmd2.Cmd.__init__(self)

.. warning::

  Shortcuts need to be created by updating the ``shortcuts`` dictionary attribute prior to calling the
  ``cmd2.Cmd`` super class ``__init__()`` method.  Moreover, that super class init method needs to be called after
  updating the ``shortcuts`` attribute  This warning applies in general to many other attributes which are not
  settable at runtime such as ``multiline_commands``, etc.


Aliases
=======

In addition to shortcuts, ``cmd2`` provides a full alias feature via the ``alias`` command which is similar to the
``alias`` command in Bash.

The syntax to create an alias is ``alias <name> <value>``. ``value`` can contain spaces and does not need
to be quoted. Ex: ``alias ls !ls -lF``

If ``alias`` is run without arguments, then a list of all aliases will be printed to stdout and are in the proper
``alias`` command syntax, meaning they can easily be reused.

The ``unalias`` is used to clear aliases. Using the ``-a`` flag will clear all aliases. Otherwise provide a list of
aliases to clear. Ex: ``unalias ls cd pwd`` will clear the aliases called ls, cd, and pwd.


Default to shell
================

Every ``cmd2`` application can execute operating-system
level (shell) commands with ``shell`` or a ``!``
shortcut::

  (Cmd) shell which python
  /usr/bin/python
  (Cmd) !which python
  /usr/bin/python

However, if the parameter ``default_to_shell`` is
``True``, then *every* command will be attempted on
the operating system.  Only if that attempt fails
(i.e., produces a nonzero return value) will the
application's own ``default`` method be called.

::

  (Cmd) which python
  /usr/bin/python
  (Cmd) my dog has fleas
  sh: my: not found
  *** Unknown syntax: my dog has fleas

Quit on SIGINT
==============

On many shells, SIGINT (most often triggered by the user
pressing Ctrl+C) only cancels the current line, not the
entire command loop. By default, a ``cmd2`` application will quit
on receiving this signal. However, if ``quit_on_sigint`` is
set to ``False``, then the current line will simply be cancelled.

::

  (Cmd) typing a comma^C
  (Cmd)


Timing
======

Setting ``App.timing`` to ``True`` outputs timing data after
every application command is executed.  |settable|

Echo
====

If ``True``, each command the user issues will be repeated
to the screen before it is executed.  This is particularly
useful when running scripts.

Debug
=====

Setting ``App.debug`` to ``True`` will produce detailed error stacks
whenever the application generates an error.  |settable|

.. |settable| replace:: The user can ``set`` this parameter
                        during application execution.
                        (See :ref:`parameters`)

.. _parameters:

Other user-settable parameters
==============================

A list of all user-settable parameters, with brief
comments, is viewable from within a running application
with::

    (Cmd) set --long
    colors: True                   # Colorized output (*nix only)
    continuation_prompt: >         # On 2nd+ line of input
    debug: False                   # Show full error stack on error
    echo: False                    # Echo command issued into output
    editor: vim                    # Program used by ``edit``
    feedback_to_output: False      # include nonessentials in `|`, `>` results
    locals_in_py: False            # Allow access to your application in py via self
    prompt: (Cmd)                  # The prompt issued to solicit input
    quiet: False                   # Don't print nonessential feedback
    timing: False                  # Report execution times

Any of these user-settable parameters can be set while running your app with the ``set`` command like so::

    set colors False

