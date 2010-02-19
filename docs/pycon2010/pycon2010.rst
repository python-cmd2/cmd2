================================================
Easy command-line interpreters with cmd and cmd2
================================================

:author:  Catherine Devlin
:date:    2010-02-20

Quit scribbling
===============

Slides are *already* posted at
homepage: http://pypi.python.org/pypi/cmd2

Web 2.0
=======

.. image:: web-2-0-logos.gif
   :height: 350px
   
But first...
============

.. image:: sargon.jpg
   :height: 250px

.. image:: akkad.png
   :height: 250px
   
Sargon the Great
  Founder of Akkadian Empire
  
.. twenty-third century BC

In between
==========

.. image:: apple.jpg
   :height: 250px
 
Command-Line Interface
  Unlike the Akkadian Empire, 
  the CLI will never die.

Defining CLI
============

Also known as
  
- "Line-oriented command interpreter"
- "Command-line interface"
- "Shell"

1. Accepts free text input at prompt
2. Outputs lines of text
3. (repeat)

Examples
========

* Bash, Korn, zsh
* Python shell
* screen
* Zork
* SQL clients: psql, SQL*\Plus, mysql...
* ed

.. ``ed`` proves that CLI is sometimes the wrong answer.

!= Command Line Utilities
=========================

(``ls``, ``grep``, ``ping``, etc.)

1. Accepts arguments at invocation
2. executes
3. terminates

Use ``sys.argv``, ``optparse``

!="Text User Interface", "Console"
==================================

* Use entire (session) screen
* I/O is *not* line-by-line
* See ``curses``, ``urwid``

.. image:: urwid.png
   :height: 250px
   

Decide your priorities
======================

.. image:: strategy.png
   :height: 350px
   
A ``cmd`` app: pirate.py
========================

::

   from cmd import Cmd
   
   class Pirate(Cmd):
       pass
   
   pirate = Pirate()
   pirate.cmdloop()

.. Nothing here... but history and help

.. ctrl-r for bash-style history

Fundamental prrrinciple
=======================

.. class:: huge
     
   Transform ``(Cmd) foo a b c``  
   
   to ``self.do_foo('a b c')``

``do_``-methods: pirate2.py
===========================

::

   class Pirate(Cmd):
       gold = 3
       def do_loot(self, arg):
           'Seize booty frrrom a passing ship.'
           self.gold += 1
           print('Now we gots {0} doubloons'.format(self.gold))
       def do_drink(self, arg):
           'Drown your sorrrows in rrrum.'
           self.gold -= 1
           print('Now we gots {0} doubloons'.format(self.gold))

.. do_methods; more help           

Hooks
=====

.. image:: hook.jpg
   :height: 250px

preloop, postloop, precmd, postcmd

Hooks: pirate3.py
=================

::

    def do_loot(self, arg):
        'Seize booty from a passing ship.'
        self.gold += 1
    def do_drink(self, arg):
        'Drown your sorrrows in rrrum.'        
        self.gold -= 1
    def precmd(self, line):
        self.initial_gold = self.gold
        return line
    def postcmd(self, stop, line):   
        if self.gold != self.initial_gold:
            print('Now we gots {0} doubloons'.format(self.gold))
           
Arguments: pirate4.py
=====================

::

        def do_drink(self, arg):
            '''Drown your sorrrows in rrrum.
            
            drink [n] - drink [n] barrel[s] o' rum.'''  
            try:
                self.gold -= int(arg)
            except:
                if arg:
                    print('''What's "{0}"?  I'll take rrrum.'''
                          .format(arg))
                self.gold -= 1            
        
quitting: pirate5.py
====================

::

    def postcmd(self, stop, line):   
        if self.gold != self.initial_gold:
            print('Now we gots {0} doubloons'.format(self.gold))
        if self.gold < 0:
            print("Off to debtorrr's prison.  Game overrr.")
            return True
        return stop
    def do_quit(self, arg):
        print("Quiterrr!")
        return True    

prompts and defaults: pirate6.py
================================

::

    prompt = 'arrr> '
    def default(self, line):
        print('What mean ye by "{0}"?'
              .format(line))

Other CLI packages
==================
 
 * cmdlin
 * cmd2                      

Demo
====

Convert ``cmd`` app to ``cmd2``

cmd2
====

.. image:: schematic.png
   :height: 350px

Absolutely free
===============

    * Script files
    * Commands at invocation
    * Output redirection    
    * Python
    * Transcript-based testing

But wait, there's more
======================

    * Abbreviated commands
    * Shell commands
    * Quitting
    * Timing
    * Echo
    * Debug
    
For a few keystrokes more...
============================

    * Default to shell
    * Color output
    * Shortcuts
    * Multiline commands
    * Environment variables

Minor changes: pirate7.py
=========================    

::

    default_to_shell = True
    multilineCommands = ['sing']
    terminators = Cmd.terminators + ['...']
    songcolor = 'blue'
    settable = Cmd.settable + 'songcolor Color to ``sing`` in (red/blue/green/cyan/magenta, bold, underline)'
    Cmd.shortcuts.update({'~': 'sing'})
    def do_sing(self, arg):
        print(self.colorize(arg, self.songcolor))
    
Now how much would you pay?
===========================

    * options / flags
    * Quiet (suppress feedback) 
    * BASH-style ``select``
    * Parsing: terminators, suffixes
        
Options: pirate8.py
===================

::

    def do_yo(self, arg, opts):
        chant = ['yo'] + ['ho'] * opts.ho
        separator = ', ' if opts.commas else ' '
        chant = separator.join(chant)
	        print('{0} and a bottle of {1}'
                      .format(chant, arg))

Serious example: sqlpython
==========================

``cmd``-based app by Luca Canali @ CERN

Replacement for Oracle SQL\*Plus

Now ``cmd2``-based; postgreSQL; MySQL

sqlpython features
==================

* from ``cmd2``: scripts, redirection,
  py, etc.
* multiple connections
* UNIX: ls, cat, grep
* Special output

File reporter
=============

Gather info: Python

Store: postgresql

Report: html

Thank you
=========

pypi.

catherinedevlin.blogspot.com

catherinedevlin.pythoneers.com


