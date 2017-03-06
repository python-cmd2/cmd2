.. cmd2 documentation for integration with other tools

Integrating cmd2 with external tools
====================================

Throughout this documentation we have focused on the **90%** use case, that is the use case we believe around 90+% of
our user base is looking for.  This focuses on ease of use and the best out-of-the-box experience where developers get
the most functionality for the least amount of effort.  We are talking about running cmd2 applications with the
``cmdloop()`` method::

    from cmd2 import Cmd
    class App(Cmd):
        # customized attributes and methods here
    app = App()
    app.cmdloop()

However, there are some limitations to this way of using
``cmd2``, mainly that ``cmd2`` owns the inner loop of a program.  This can be unnecessarily restrictive and can prevent
using libraries which depend on controlling their own event loop.


Integrating cmd2 with event loops
---------------------------------

Many Python concurrency libraries involve or require an event loop which they are in control of such as asyncio_,
gevent_, Twisted_, etc.

.. _asyncio: https://docs.python.org/3/library/asyncio.html
.. _gevent: http://www.gevent.org/
.. _Twisted: https://twistedmatrix.com

``cmd2`` applications can be executed in a fashion where ``cmd2`` doesn't own the main loop for the program by using
code like the following::

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
        app.onecmd_plus_hooks(cmd_line_text)

        app.postloop()

The **onecmd_plus_hooks()** method will do the following to execute a single ``cmd2`` command in a normal fashion:

#. Parse the command line text
#. Execute postparsing_precmd()
#. Add the command to the history
#. Apply output redirection, if present
#. Execute precmd()
#. Execute onecmd() - this is what actually runs the command
#. Execute postcmd()
#. Undo output rediriection (if present) and perform piping, if present
#. Execute postparsing_postcmd()

Running in this fashion enables the ability to integrate with an external event loop.  However, how to integrate with
any specific event loop is beyond the scope of this documentation.  Please note that running in this fashion comes with
several disadvantages, including:

* Requires the developer to write more code
* Does not support transcript testing
* Does not allow commands at invocation via command-line arguments


