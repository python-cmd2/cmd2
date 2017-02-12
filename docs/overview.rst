
========
Overview
========

``cmd2`` is an extension of cmd_, the Python Standard Library's module for
creating simple interactive command-line applications.

``cmd2`` can be used as a drop-in replacement for cmd_.  Simply importing ``cmd2``
in place of cmd_ will add many features to an application without any further
modifications.

Understanding the use of cmd_ is the first step in learning the use of ``cmd2``.
Once you have read the cmd_ docs, return here to learn the ways that ``cmd2``
differs from cmd_.

.. note::

   ``cmd2`` is not quite a drop-in replacement for cmd_.
   The `cmd.emptyline() <https://docs.python.org/3/library/cmd.html#cmd.Cmd.emptyline>`_ function is called
   when an empty line is entered in response to the prompt. By default, in cmd_ if this method is not overridden, it
   repeats and executes the last nonempty command entered.  However, no end user we have encountered views this as
   expected or desirable default behavior.  Thus, the default behvior in ``cmd2`` is to simply go to the next line
   and issue the prompt again.  At this time, cmd2 completely ignores empty lines and the base class cmd.emptyline()
   method never gets called and thus the emptyline() behavior cannot be overriden.

.. _cmd: https://docs.python.org/3/library/cmd.html
