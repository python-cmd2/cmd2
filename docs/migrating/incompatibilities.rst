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
as expected or desirable default behavior. ``cmd2`` completely ignores empty
lines and the base class ``cmd.emptyline()`` method never gets called and thus
the empty line behavior cannot be overridden.


Cmd.identchars
--------------

In cmd_, the `Cmd.identchars
<https://docs.python.org/3/library/cmd.html#cmd.Cmd.identchars>`_ attribute
contains the string of characters accepted for command names. cmd_ uses those
characters to split the first "word" of the input, without requiring the user
to type a space. For example, if ``identchars`` contained a string of all
alphabetic characters, the user could enter a command like ``L20`` and it would
be interpreted as the command ``L`` with the first argument of ``20``.

Since version 0.9.0, ``cmd2`` has ignored ``identchars``; the parsing logic in
``cmd2`` splits the command and arguments on whitespace. We opted for this
breaking change because while cmd_ supports unicode, using non-ascii unicode
characters in command names while simultaneously using ``identchars``
functionality can be somewhat painful. Requiring white space to delimit
arguments also ensures reliable operation of many other useful ``cmd2``
features, including :ref:`features/completion:Completion` and
:ref:`features/shortcuts_aliases_macros:Shortcuts, Aliases, and Macros`.

If you really need this functionality in your app, you can add it back in by
writing a :ref:`Postparsing Hook <features/hooks:Postparsing Hooks>`.


Cmd.cmdqueue
------------

In cmd_, the `Cmd.cmdqueue
<https://docs.python.org/3/library/cmd.html#cmd.Cmd.cmdqueue>`_ attribute
contains a list of queued input lines. The cmdqueue list is checked in
``cmdloop()`` when new input is needed; if it is nonempty, its elements will be
processed in order, as if entered at the prompt.

Since version 0.9.13 ``cmd2`` has removed support for ``Cmd.cmdqueue``. Because
``cmd2`` supports running commands via the main ``cmdloop()``, text scripts,
Python scripts, transcripts, and history replays, the only way to preserve
consistent behavior across these methods was to eliminate the command queue.
Additionally, reasoning about application behavior is much easier without this
queue present.
