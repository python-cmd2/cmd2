py 3

Web 2.0
=======

.. image:: web-2-0-logos.gif
   :height: 300 px
   
But first...
============

.. image:: sargon.jpg
   :height: 300 px
   
Sargon the Great founded the Akkadian Empire
in the twenty-third century BC.

In between
==========

.. image:: apple.jpg
   :height: 300 px
 
Unlike the Akkadian Empire, the CLI will never disappear.

line-oriented command interpreter
command-line interface
text user interface
terminal user interface
console
shell

Defining
========

Prompt accepts free text input
Outputs lines of text
CLI environment persists

Examples
========

Bash, Korn, zsh
Python shell
screen
Zork
ed
SQL clients: psql, SQL*\Plus, mysql...

!= Command Line Utilities
=========================

Accept single set of arguments at 
invocation, execute, terminate

dir
grep
ping

sys.argv
optparse

!= Text User Interfaces
=======================

("console")

Use entire (session) screen
Not line-by-line

.. image:: urwid.png
   :height: 300px
   
curses
urwid


foo a b c ->
self.do_foo('a b c')
self.default('foo a b c')

pirate.py
=========

::

   from cmd import Cmd
   
   class Pirate(Cmd):
       pass
   
   pirate = Pirate()
   pirate.cmdloop()

history: cursor
ctrl-r
help

