Alternatives
============

For programs that do not interact with the user in a continuous loop - programs
that simply accept a set of arguments from the command line, return results,
and do not keep the user within the program's environment - all you need are
sys_\ .argv (the command-line arguments) and argparse_ (for parsing UNIX-style
options and flags).  Though some people may prefer docopt_ or click_ to
argparse_.

.. _sys: https://docs.python.org/3/library/sys.html
.. _argparse: https://docs.python.org/3/library/argparse.html
.. _docopt: https://pypi.org/project/docopt
.. _click: https://click.palletsprojects.com


The curses_ module produces applications that interact via a plaintext terminal
window, but are not limited to simple text input and output; they can paint the
screen with options that are selected from using the cursor keys.  However,
programming a curses_-based application is not as straightforward as using
cmd_.

.. _curses: https://docs.python.org/3/library/curses.html
.. _cmd: https://docs.python.org/3/library/cmd.html

Several Python packages exist for building interactive command-line
applications approximately similar in concept to cmd_ applications.  None of
them share ``cmd2``'s close ties to cmd_, but they may be worth investigating
nonetheless. Two of the most mature and full featured are:

  * `Python Prompt Toolkit`_
  * Click_

.. _`Python Prompt Toolkit`: https://github.com/prompt-toolkit/python-prompt-toolkit

`Python Prompt Toolkit`_ is a library for building powerful interactive command
lines and terminal applications in Python.  It provides a lot of advanced
visual features like syntax highlighting, bottom bars, and the ability to
create fullscreen apps.

Click_ is a Python package for creating beautiful command line interfaces in a
composable way with as little code as necessary.  It is more geared towards
command line utilities instead of command line interpreters, but it can be used
for either.

Getting a working command-interpreter application based on either `Python
Prompt Toolkit`_ or Click_ requires a good deal more effort and boilerplate
code than ``cmd2``.  ``cmd2`` focuses on providing an excellent out-of-the-box
experience with as many useful features as possible built in for free with as
little work required on the developer's part as possible.  We believe that
``cmd2`` provides developers the easiest way to write a command-line
interpreter, while allowing a good experience for end users.  If you are
seeking a visually richer end-user experience and don't mind investing more
development time, we would recommend checking out `Python Prompt Toolkit`_.
