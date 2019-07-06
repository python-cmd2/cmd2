Incompatibilities
=================

.. _cmd: https://docs.python.org/3/library/cmd.html

``cmd2`` strives to be drop-in compatible with cmd_, however there are a few
things that are not.


cmd.emptyline()
---------------

The `cmd.emptyline()
<https://docs.python.org/3/library/cmd.html#cmd.Cmd.emptyline>`_ function is
called when an empty line is entered in response to the prompt. By default, in
cmd_ if this method is not overridden, it repeats and executes the last
nonempty command entered.  However, no end user we have encountered views this
as expected or desirable default behavior.  Thus, the default behavior in
``cmd2`` is to simply go to the next line and issue the prompt again.  At this
time, cmd2 completely ignores empty lines and the base class cmd.emptyline()
method never gets called and thus the emptyline() behavior cannot be
overridden.
