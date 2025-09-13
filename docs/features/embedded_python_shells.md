# Embedded Python Shells

## Python (optional)

If the [cmd2.Cmd][] class is instantiated with `include_py=True`, then the optional `py` command
will be present and run an interactive Python shell:

```py
from cmd2 import Cmd
class App(Cmd):
    def __init__(self):
        Cmd.__init__(self, include_py=True)
```

The Python shell can run CLI commands from you application using the object named in
`self.pyscript_name` (defaults to `app`). This wrapper provides access to execute commands in your
`cmd2` application while maintaining isolation from the full `Cmd` instance. For example, any
application command can be run with `app("command ...")`.

You may optionally enable full access to your application by setting `self.self_in_py` to `True`.
Enabling this flag adds `self` to the python session, which is a reference to your `cmd2`
application. This can be useful for debugging your application.

Any local or global variable created within the Python session will not persist in the CLI's
environment.

Anything in `self.py_locals` is always available in the Python environment.

All of these parameters are also available to Python scripts which run in your application via the
`run_pyscript` command:

- supports tab completion of file system paths
- has the ability to pass command-line arguments to the scripts invoked

This command provides a more complex and powerful scripting capability than that provided by the
simple text file scripts. Python scripts can include conditional control flow logic. See
[python_scripting.py](https://github.com/python-cmd2/cmd2/blob/main/examples/python_scripting.py)
`cmd2` and the
[conditional.py](https://github.com/python-cmd2/cmd2/blob/main/examples/scripts/conditional.py)
script for an example of how to achieve this in your own applications. See
[Scripting](./scripting.md) for an explanation of both scripting methods in `cmd2` applications.

A simple example of using `run_pyscript` is shown below along with the
[arg_printer](https://github.com/python-cmd2/cmd2/blob/main/examples/scripts/arg_printer.py) script:

```sh
(Cmd) run_pyscript examples/scripts/arg_printer.py foo bar baz
Running Python script 'arg_printer.py' which was called with 3 arguments
arg 1: 'foo'
arg 2: 'bar'
arg 3: 'baz'
```

## IPython (optional)

**If** [IPython](http://ipython.readthedocs.io) is installed on the system **and** the `cmd2.Cmd`
class is instantiated with `include_ipy=True`, then the optional `ipy` command will run an
interactive IPython shell:

```py
from cmd2 import Cmd
class App(Cmd):
    def __init__(self):
        Cmd.__init__(self, include_ipy=True)
```

The `ipy` command enters an interactive [IPython](http://ipython.readthedocs.io) session. Similar to
an interactive Python session, this shell can access your application instance via `self` if
`self.self_in_py` is `True` and any changes to your application made via `self` will persist.
However, any local or global variable created within the `ipy` shell will not persist in the CLI's
environment

Also, as in the interactive Python session, the `ipy` shell has access to the contents of
`self.py_locals` and can call back into the application using the `app` object (or your custom
name).

[IPython](http://ipython.readthedocs.io) provides many advantages, including:

> - Comprehensive object introspection
> - Get help on objects with `?`
> - Extensible tab completion, with support by default for completion of python variables and
>   keywords
> - Good built-in [ipdb](https://pypi.org/project/ipdb/) debugger

The object introspection and tab completion make IPython particularly efficient for debugging as
well as for interactive experimentation and data analysis.
