===================================
Features requiring no modifications
===================================

These features are provided "for free" to a cmd_-based application
simply by replacing ``import cmd`` with ``import cmd2 as cmd``.

Searchable command history
==========================

All cmd_-based applications have access to previous commands with 
the up- and down- cursor keys.

All cmd_-based applications on systems with the ``readline`` module
also provide `bash-like history list editing`_.

.. _`bash-like history list editing`: http://www.talug.org/events/20030709/cmdline_history.html

``cmd2`` makes a third type of history access available, consisting of these commands:

.. automethod:: cmd2.Cmd.do_history

