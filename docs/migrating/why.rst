Why Migrate to cmd2
===================

.. _cmd: https://docs.python.org/3/library/cmd.html

cmd
---

cmd_ is the Python Standard Library's module for creating simple interactive
command-line applications.
cmd_ is an extremely bare-bones framework which leaves a lot to be desired.  It
doesn't even include a built-in way to exit from an application!

Since the API provided by cmd_ provides the foundation on which ``cmd2`` is
based, understanding the use of cmd_ is the first step in learning the use of
``cmd2``. Once you have read the cmd_ docs, return here to learn the ways that
``cmd2`` differs from cmd_.

cmd2
----
``cmd2`` is a batteries-included extension of cmd_, which provides a wealth of
functionality to make it quicker and easier for developers to create
feature-rich interactive command-line applications which delight customers.

``cmd2`` can be used as a drop-in replacement for cmd_.  Simply importing
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

