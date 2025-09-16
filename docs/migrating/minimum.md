# Minimum Required Changes

[cmd2.Cmd][] subclasses [cmd.Cmd](https://docs.python.org/3/library/cmd.html#cmd.Cmd) from the
standard library, and overrides all of the methods other than `Cmd.emptyline` (`cmd2` never calls
this method). Most apps based on the standard library can be migrated to `cmd2` in just a couple of
minutes.

## Import and Inheritance

You need to change your import from this:

```py
import cmd
```

to this:

```py
import cmd2
```

Then you need to change your class definition from:

```py
class CmdLineApp(cmd.Cmd):
```

to:

```py
class CmdLineApp(cmd2.Cmd):
```

## Exiting

Have a look at the commands you created to exit your application. You probably have one called
`exit` and maybe a similar one called `quit`. You also might have implemented a `do_EOF()` method so
your program exits like many operating system shells. If all these commands do is quit the
application, you may be able to remove them. See [Exiting](../features/misc.md#exiting).

## Distribution

If you are distributing your application, you'll also need to ensure that `cmd2` is properly
installed. You will need to add the following dependency to your `pyproject.toml` or `setup.py`:

    'cmd2>=3,<4'

See [Integrate cmd2 Into Your Project](../overview/integrating.md) for more details.
