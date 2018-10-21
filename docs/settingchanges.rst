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

In addition to shortcuts, ``cmd2`` provides a full alias feature via the ``alias`` command. Aliases work in a similar
fashion to aliases in the Bash shell.

The syntax to create an alias is: ``alias create name command [args]``.

  Ex: ``alias create ls !ls -lF``

For more details run: ``help alias create``

Use ``alias list`` to see all or some of your aliases. The output of this command displays your aliases using the same command that
was used to create them. Therefore you can place this output in a ``cmd2`` startup script to recreate your aliases each time
you start the application

  Ex: ``alias list``

For more details run: ``help alias list``

Use ``alias delete`` to remove aliases

For more details run: ``help alias delete``

Macros
======

``cmd2`` provides a feature that is similar to aliases called macros. The major difference between macros and aliases
is that macros are intended to take arguments when called. These can be useful if you need to run a complex command
frequently with different arguments that appear in various parts of the command.

Arguments are expressed when creating a macro using {#} notation where {1} means the first argument.

The following creates a macro called my_macro that expects two arguments:

  macro create my_macro make_dinner -meat {1} -veggie {2}

When the macro is called, the provided arguments are resolved and the assembled
command is run. For example:

  my_macro beef broccoli ---> make_dinner -meat beef -veggie broccoli

For more details run: ``help macro create``

The macro command has ``list`` and ``delete`` subcommands that function identically to the alias subcommands of the
same name. Like aliases, macros can be created via a ``cmd2`` startup script to preserve them across application
sessions.

For more details on listing macros run: ``help macro list``

For more details on deleting macros run: ``help macro delete``


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

.. warning::
    The default SIGINT behavior will only function properly if **cmdloop** is running
    in the main thread.


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
    colors: Terminal               # Allow colorized output
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

    set colors Never

