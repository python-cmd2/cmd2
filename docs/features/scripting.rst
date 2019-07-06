Scripting
=========

Document use cases and commands for ``run_script`` and ``run_pyscript``

Comments
--------

Any command line input where the first non-whitespace character is a `#` will
be treated as a comment. This means any `#` character appearing later in the
command will be treated as a literal. The same applies to a `#` in the middle
of a multiline command, even if it is the first character on a line.

Comments can be useful in :ref:`scripts`, but would be pointless within an
interactive session.

::

  (Cmd) # this is a comment
  (Cmd) this # is not a comment
