Alternate Event Loops
=====================

Throughout this documentation we have focused on the **90%** use case, that is
the use case we believe around **90+%** of our user base is looking for.  This
focuses on ease of use and the best out-of-the-box experience where developers
get the most functionality for the least amount of effort.  We are talking
about running ``cmd2`` applications with the ``cmdloop()`` method::

    from cmd2 import Cmd
    class App(Cmd):
        # customized attributes and methods here
    app = App()
    app.cmdloop()

However, there are some limitations to this way of using ``cmd2``, mainly that
``cmd2`` owns the inner loop of a program.  This can be unnecessarily
restrictive and can prevent using libraries which depend on controlling their
own event loop.

Many Python concurrency libraries involve or require an event loop which they
are in control of such as asyncio_, gevent_, Twisted_, etc.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _gevent: http://www.gevent.org/
.. _Twisted: https://twistedmatrix.com

``cmd2`` applications can be executed in a fashion where ``cmd2`` doesn't own
the main loop for the program by using code like the following::

    import cmd2

    class Cmd2EventBased(cmd2.Cmd):
        def __init__(self):
            cmd2.Cmd.__init__(self)

        # ... your class code here ...

    if __name__ == '__main__':
        app = Cmd2EventBased()
        app.preloop()

        # Do this within whatever event loop mechanism you wish to run a single command
        cmd_line_text = "help history"
        app.runcmds_plus_hooks([cmd_line_text])

        app.postloop()

The :meth:`~cmd2.Cmd.runcmds_plus_hooks()` method runs multiple commands via
:meth:`~cmd2.Cmd.onecmd_plus_hooks`.

The :meth:`~cmd2.Cmd.onecmd_plus_hooks()` method will do the following to
execute a single command in a normal fashion:

#. Parse user input into a :class:`~cmd2.Statement` object
#. Call methods registered with :meth:`~cmd2.Cmd.register_postparsing_hook()`
#. Redirect output, if user asked for it and it's allowed
#. Start timer
#. Call methods registered with :meth:`~cmd2.Cmd.register_precmd_hook`
#. Call :meth:`~cmd2.Cmd.precmd` - for backwards compatibility with ``cmd.Cmd``
#. Add statement to :ref:`features/history:History`
#. Call `do_command` method
#. Call methods registered with :meth:`~cmd2.Cmd.register_postcmd_hook()`
#. Call :meth:`~cmd2.Cmd.postcmd` - for backwards compatibility with
   ``cmd.Cmd``
#. Stop timer and display the elapsed time
#. Stop redirecting output if it was redirected
#. Call methods registered with
   :meth:`~cmd2.Cmd.register_cmdfinalization_hook()`

Running in this fashion enables the ability to integrate with an external event
loop.  However, how to integrate with any specific event loop is beyond the
scope of this documentation.  Please note that running in this fashion comes
with several disadvantages, including:

* Requires the developer to write more code
* Does not support transcript testing
* Does not allow commands at invocation via command-line arguments
