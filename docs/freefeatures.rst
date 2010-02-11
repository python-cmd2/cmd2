===================================
Features requiring no modifications
===================================

These features are provided "for free" to a cmd_-based application
simply by replacing ``import cmd`` with ``import cmd2 as cmd``.

Script files
============

Commands can be loaded from, run from, and saved to text files.

.. automethod:: cmd2.Cmd.do_load

Output redirection
==================

As in a Unix shell, output of a command can be redirected:

  - sent to a file with ``>``, as in ``mycommand args > filename.txt``
  - piped (``|``) as input to operating-system commands, as in
    ``mycommand args | wc``
  - sent to the paste buffer, ready for the next Copy operation, by
    ending with a bare ``>``, as in ``mycommand args >``..  Redirecting
    to paste buffer requires software to be installed on the operating
    system, pywin32_ on Windows or xclip_ on *nix.
    
.. _pywin32:: http://sourceforge.net/projects/pywin32/
.. _xclip:: http://www.cyberciti.biz/faq/xclip-linux-insert-files-command-output-intoclipboard/

  
operating-system programs, like 

Commands at start
=================

Python
======

Searchable command history
==========================

All cmd_-based applications have access to previous commands with 
the up- and down- cursor keys.

All cmd_-based applications on systems with the ``readline`` module
also provide `bash-like history list editing`_.

.. _`bash-like history list editing`: http://www.talug.org/events/20030709/cmdline_history.html

``cmd2`` makes a third type of history access available, consisting of these commands:

.. automethod:: cmd2.Cmd.do_history

Transcript-based testing
========================
