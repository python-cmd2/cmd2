Removing Builtin Commands
=========================

Show how to remove built in comamnds. Say for example you don't like the
``quit`` command included in ``cmd2``. Your application has to subclass
``cmd2.Cmd`` to work, which means you inherit the ``quit`` command. Here's how
to remove it.
