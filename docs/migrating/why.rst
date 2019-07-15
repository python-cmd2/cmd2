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


Free Features
-------------

After switching from cmd_ to ``cmd2``, your application will have the following
new features and capabilities, without you having to do anything:

- More robust :ref:`features/history:History`. Both cmd_ and ``cmd2`` have
  readline history, but ``cmd2`` also has a robust ``history`` command which
  allows you to edit prior commands in a text editor of your choosing, re-run
  multiple commands at a time, and save prior commands as a script to be
  executed later.

- Users can redirect output to a file or pipe it to some other operating system
  command. You did remember to use ``self.stdout`` instead of ``sys.stdout`` in
  all of your print functions, right? If you did, then this will work out of
  the box. If you didn't, you'll have to go back and fix them. Before you do,
  you might consider the various ways ``cmd2`` has of
  :ref:`features/generating_output:Generating Output`.

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


Next Steps
----------

In addition to the features you get with no additional work, ``cmd2`` offers a
broad range of additional capabilties which can be easily added to your
application. :ref:`migrating/next_steps:Next Steps` has some ideas of where
you can start, or you can dig in to all the :ref:`features/index:Features`.
