===================================
Features requiring no modifications
===================================

These features are provided "for free" to a cmd_-based application
simply by replacing ``import cmd`` with ``import cmd2 as cmd``.

Script files
============

Commands can be loaded and run from text files.

.. automethod:: cmd2.Cmd.do_load

.. automethod:: cmd2.Cmd.do_save

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

  
Commands at invocation
======================

You can send commands to your app as you invoke it by
including them as extra arguments to the program.
``cmd2`` interprets each argument as a separate 
command, so you should enclose each command in 
quotation marks if it is more than a one-word command.

::

  cat@eee:~/proj/cmd2/example$ python example.py "say hello" "say Gracie" quit
  hello
  Gracie
  cat@eee:~/proj/cmd2/example$ 

Python
======

::

The ``py`` command will run its arguments as a Python
command.  Entered without arguments, it enters an
interactive Python session.  That session can call
"back" to your application with ``cmd("")``.  Through
``self``, it also has access to your application
instance itself.  (If that thought terrifies you,
you can set the ``locals_in_py`` parameter to ``False``.
See see :ref:`parameters`)

::

	(Cmd) py print("-".join("spelling"))
	s-p-e-l-l-i-n-g
	(Cmd) py
	Python 2.6.4 (r264:75706, Dec  7 2009, 18:45:15) 
	[GCC 4.4.1] on linux2
	Type "help", "copyright", "credits" or "license" for more information.
	(CmdLineApp)

		py <command>: Executes a Python command.
		py: Enters interactive Python mode.
		End with `Ctrl-D` (Unix) / `Ctrl-Z` (Windows), `quit()`, 'exit()`.
		Non-python commands can be issued with `cmd("your command")`.
		
	>>> import os
	>>> os.uname()
	('Linux', 'eee', '2.6.31-19-generic', '#56-Ubuntu SMP Thu Jan 28 01:26:53 UTC 2010', 'i686')
	>>> cmd("say --piglatin {os}".format(os=os.uname()[0]))
	inuxLay
	>>> self.prompt
	'(Cmd) '
	>>> self.prompt = 'Python was here > '
	>>> quit()
	Python was here > 

Searchable command history
==========================

All cmd_-based applications have access to previous commands with 
the up- and down- cursor keys.

All cmd_-based applications on systems with the ``readline`` module
also provide `bash-like history list editing`_.

.. _`bash-like history list editing`: http://www.talug.org/events/20030709/cmdline_history.html

``cmd2`` makes a third type of history access available, consisting of these commands:

.. automethod:: cmd2.Cmd.do_history

.. automethod:: cmd2.Cmd.do_list

.. automethod:: cmd2.Cmd.do_run

Quitting the application
========================

``cmd2`` pre-defines a ``quit`` command for you (with 
synonyms ``exit`` and simply ``q``).
It's trivial, but it's one less thing for you to remember.

Transcript-based testing
========================
