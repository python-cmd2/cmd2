============================
Alternatives to cmd and cmd2
============================

For programs that do not interact with the user in a continuous loop - 
programs that simply accept a set of arguments from the command line, return 
results, and do not keep the user within the program's environment - all
you need are sys_\ .argv (the command-line arguments) and optparse_
(for parsing UNIX-style options and flags).

.. _optparse: http://docs.python.org/library/optparse.html#module-optparse

.. _sys: http://docs.python.org/library/sys.html#module-sys

.. _curses: http://docs.python.org/library/curses.html#module-curses

.. _cmd: http://docs.python.org/library/cmd.html#module-cmd

The curses_ module produces applications that interact via a plaintext
terminal window, but are not limited to simple text input and output;
they can paint the screen with options that are selected from using the
cursor keys.  However, programming a curses_-based application is not as
straightforward as using cmd_.

Several packages in PyPI enable interactive command-line applications
approximately similar in concept to cmd_ applications.  None of them 
share cmd2's close ties to cmd, but they may be worth investigating
nonetheless.

  * CmdLoop_
  * cly_
  * CmDO_ (As of Feb. 2010, webpage is missing.)
  * pycopia-CLI_
  
cmdln_, another package in PyPI, is an extension to cmd_ and, though it
doesn't retain full cmd_ compatibility, shares its basic structure with
cmd_.

.. _cmdln: http://pypi.python.org/pypi/cmdln

.. _CmdLoop: http://pypi.python.org/pypi/CmdLoop

.. _cly: http://pypi.python.org/pypi/cly

.. _CmDO: http://pypi.python.org/pypi/CmDO/0.7

.. _pycopia-CLI: http://pypi.python.org/pypi/pycopia-CLI/1.0

I've found several alternatives to cmd in the Cheese Shop - CmdLoop, cly, CMdO, and pycopia. cly looks wonderful, but I haven't been able to get it working under Windows, and that's a show-stopper for many potential sqlpython users. In any case, none of the alternatives are based on cmd - they're written from scratch, which means that a cmd-based app would need complete rewriting to use them. I like sticking close to the Standard Library whenever possible. cmd2 lets you do that.

