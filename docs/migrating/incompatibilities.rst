Incompatibilities
=================

.. _cmd: https://docs.python.org/3/library/cmd.html

``cmd2`` strives to be drop-in compatible with cmd_, however there are a few
incompatibilities.


Cmd.emptyline()
---------------

The `Cmd.emptyline()
<https://docs.python.org/3/library/cmd.html#cmd.Cmd.emptyline>`_ function is
called when an empty line is entered in response to the prompt. By default, in
cmd_ if this method is not overridden, it repeats and executes the last
nonempty command entered. However, no end user we have encountered views this
as expected or desirable default behavior. Thus, the default behavior in
``cmd2`` is to simply go to the next line and issue the prompt again. At this
time, ``cmd2`` completely ignores empty lines and the base class
cmd.emptyline() method never gets called and thus the emptyline() behavior
cannot be overridden.


Cmd.identchars
--------------

In cmd_, the `Cmd.identchars
<https://docs.python.org/3/library/cmd.html#cmd.Cmd.identchars>`_ attribute
contains the string of characters accepted for command names. cmd_ uses those
characters to split the first "word" of the input, without requiring the user
to type a space. For example, if ``identchars`` contained a string of all alphabetic
characters, the user could enter a command like ``L20`` and it would be interpreted
as the command ``L`` with the first argument of ``20``.

Since version 0.9.0, ``cmd2`` has ignored ``identchars``; the parsing logic in
``cmd2`` splits the command and arguments on whitespace. While cmd_ technically
supports unicode, as a practical matter, it would be nearly impossible to
enumerate all the "alphabetic" unicode characters in the ``identchars``
attribute.

If you really need this functionality in your app, you can add it back in by
writing a :ref:`Postparsing Hook <features/hooks:Postparsing Hooks>`.


Cmd.cmdqueue
------------
In cmd_, the `Cmd.cmdqueue
<https://docs.python.org/3/library/cmd.html#cmd.Cmd.cmdqueue>`_ attribute
contains A list of queued input lines. The cmdqueue list is checked in
``cmdloop()`` when new input is needed; if it is nonempty, its elements will be
processed in order, as if entered at the prompt.

Since version 0.9.13 ``cmd2`` has removed support for ``Cmd.cmdqueue``.
Because ``cmd2`` supports running commands via the main ``cmdloop()``, text
scripts, Python scripts, transcripts, and history replays, the only way to
preserve consistent behavior across these methods was to eliminate the command
queue. Additionally, reasoning about application behavior is much easier
without this queue present.

If developers need this sort of thing, they can add it in their application.
However, if they are not extremely careful there would likely be unintended
consequences.
