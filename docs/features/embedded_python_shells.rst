Embedded Python Shells
======================

The ``py`` command will run its arguments as a Python command.  Entered without
arguments, it enters an interactive Python session.  The session can call
"back" to your application through the name defined in ``self.pyscript_name``
(defaults to ``app``).  This wrapper provides access to execute commands in
your ``cmd2`` application while maintaining isolation.

You may optionally enable full access to to your application by setting
``self_in_py`` to ``True``.  Enabling this flag adds ``self`` to the python
session, which is a reference to your ``cmd2`` application. This can be useful
for debugging your application.

The ``app`` object (or your custom name) provides access to application
commands through raw commands.  For example, any application command call be
called with ``app("<command>")``.

::

    >>> app('say --piglatin Blah')
    lahBay

More Python examples:

::

    (Cmd) py print("-".join("spelling"))
    s-p-e-l-l-i-n-g
    (Cmd) py
    Python 3.5.3 (default, Jan 19 2017, 14:11:04)
    [GCC 6.3.0 20170118] on linux
    Type "help", "copyright", "credits" or "license" for more information.
    (CmdLineApp)

    End with `Ctrl-D` (Unix) / `Ctrl-Z` (Windows), `quit()`, `exit()`.
    Non-python commands can be issued with: app("your command")
    Run python code from external script files with: run("script.py")

    >>> import os
    >>> os.uname()
    ('Linux', 'eee', '2.6.31-19-generic', '#56-Ubuntu SMP Thu Jan 28 01:26:53 UTC 2010', 'i686')
    >>> app("say --piglatin {os}".format(os=os.uname()[0]))
    inuxLay
    >>> self.prompt
    '(Cmd) '
    >>> self.prompt = 'Python was here > '
    >>> quit()
    Python was here >

Using the ``py`` command is tightly integrated with your main ``cmd2``
application and any variables created or changed will persist for the life of
the application::

    (Cmd) py x = 5
    (Cmd) py print(x)
    5

The ``py`` command also allows you to run Python scripts via ``py
run('myscript.py')``. This provides a more complicated and more powerful
scripting capability than that provided by the simple text file scripts
discussed in :ref:`features/scripting:Scripting`.  Python scripts can include
conditional control flow logic.  See the **python_scripting.py** ``cmd2``
application and the **script_conditional.py** script in the ``examples`` source
code directory for an example of how to achieve this in your own applications.

Using ``py`` to run scripts directly is considered deprecated.  The newer
``run_pyscript`` command is superior for doing this in two primary ways:

- it supports tab completion of file system paths
- it has the ability to pass command-line arguments to the scripts invoked

There are no disadvantages to using ``run_pyscript`` as opposed to ``py
run()``.  A simple example of using ``run_pyscript`` is shown below  along with
the arg_printer_ script::

    (Cmd) run_pyscript examples/scripts/arg_printer.py foo bar baz
    Running Python script 'arg_printer.py' which was called with 3 arguments
    arg 1: 'foo'
    arg 2: 'bar'
    arg 3: 'baz'

.. note::

    If you want to be able to pass arguments with spaces to commands, then we
    strongly recommend using one of the decorators, such as
    ``with_argument_list``.  ``cmd2`` will pass your **do_*** methods a list of
    arguments in this case.

    When using this decorator, you can then put arguments in quotes like so::

        $ examples/arg_print.py
        (Cmd) lprint foo "bar baz"
        lprint was called with the following list of arguments: ['foo', 'bar baz']

.. _arg_printer:
   https://github.com/python-cmd2/cmd2/blob/master/examples/scripts/arg_printer.py


IPython (optional)
------------------

**If** IPython_ is installed on the system **and** the ``cmd2.Cmd`` class is
instantiated with ``use_ipython=True``, then the optional ``ipy`` command will
be present::

    from cmd2 import Cmd
    class App(Cmd):
        def __init__(self):
            Cmd.__init__(self, use_ipython=True)

The ``ipy`` command enters an interactive IPython_ session.  Similar to an
interactive Python session, this shell can access your application instance via
``self`` and any changes to your application made via ``self`` will persist.
However, any local or global variable created within the ``ipy`` shell will not
persist. Within the ``ipy`` shell, you cannot call "back" to your application
with ``cmd("")``, however you can run commands directly like so::

    self.onecmd_plus_hooks('help')

IPython_ provides many advantages, including:

    * Comprehensive object introspection
    * Get help on objects with ``?``
    * Extensible tab completion, with support by default for completion of
      python variables and keywords
    * Good built-in ipdb_ debugger

The object introspection and tab completion make IPython particularly efficient
for debugging as well as for interactive experimentation and data analysis.

.. _IPython: http://ipython.readthedocs.io
.. _ipdb: https://pypi.org/project/ipdb/


