Why cmd2
========

.. _cmd: https://docs.python.org/3/library/cmd.html

cmd
---

cmd_ is the Python Standard Library's module for creating simple interactive
command-line applications. cmd_ is an extremely bare-bones framework which
leaves a lot to be desired.  It doesn't even include a built-in way to exit
from an application!

Since the API provided by cmd_ provides the foundation on which ``cmd2`` is
based, understanding the use of cmd_ is the first step in learning the use of
``cmd2``. Once you have read the cmd_ docs, return here to learn the ways that
``cmd2`` differs from cmd_.


cmd2
----

``cmd2`` is a batteries-included extension of cmd_, which provides a wealth of
functionality to make it quicker and easier for developers to create
feature-rich interactive command-line applications which delight customers.

``cmd2`` can be used as a drop-in replacement for cmd_ with a few minor
discrepancies as discussed in the
:ref:`migrating/incompatibilities:Incompatibilities` section.  Simply importing
``cmd2`` in place of cmd_ will add many features to an application without any
further modifications.  Migrating to ``cmd2`` will also open many additional
doors for making it possible for developers to provide a top-notch interactive
command-line experience for their users.

``cmd2`` provides a full-featured framework for creating professional-quality
interactive command-line applications. A few of the highlights of ``cmd2``
include:

* Applications created are full-featured shells in their own right with ability
  to call shell commands, redirect command output, pipe command output to shell
  commands, etc.
* Superior tab-completion capabilities, especially when using included argparse
  decorators
* Both Python and ASCII text application scripting is built-in
* Ability to run non-interactively for automation purposes


Free Features
-------------

After switching from cmd_ to ``cmd2``, your application will have the following
new features and capabilities, without you having to do anything:

- More robust :ref:`features/history:History`. Both cmd_ and ``cmd2`` have readline
  history, but ``cmd2`` also has a robust ``history`` command which allows you
  to edit prior commands in a text editor of your choosing, re-run multiple
  commands at a time, and save prior commands as a script to be executed later.

- Users can load script files, which contain a series of commands
  to be executed.

- Users can create :ref:`features/shortcuts_aliases_macros:Shortcuts, Aliases,
  and Macros` to reduce the typing required for repetitive commands.

- Embedded python shell allows a user to execute python code from within your
  ``cmd2`` app. How meta.

- :ref:`features/clipboard:Clipboard Integration` allows you to save command
  output to the operating system clipboard.

- A built-in :ref:`features/misc:Timer` can show how long it takes a command to
  execute

- A :ref:`Transcript <features/transcripts:Transcripts>` is a file which
  contains both the input and output of a successful session of a
  ``cmd2``-based app. The transcript can be played back into the app as a unit
  test.

