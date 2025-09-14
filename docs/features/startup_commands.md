# Startup Commands

`cmd2` provides a couple different ways for running commands immediately after your application
starts up:

1.  Commands at Invocation
1.  Startup Script

Commands run as part of a startup script are always run immediately after the application finishes
initializing so they are guaranteed to run before any _Commands At Invocation_.

## Commands At Invocation

You can send commands to your app as you invoke it by including them as extra arguments to the
program. `cmd2` interprets each argument as a separate command, so you should enclose each command
in quotation marks if it is more than a one-word command. You can use either single or double quotes
for this purpose.

    $ python examples/transcript_example.py "say hello" "say Gracie" quit
    hello
    Gracie

You can end your commands with a **quit** command so that your `cmd2` application runs like a
non-interactive command-line utility (CLU). This means that it can then be scripted from an external
application and easily used in automation.

!!! note

    If you wish to disable cmd2's consumption of command-line arguments, you can do so by setting the `allow_cli_args` argument of your [cmd2.Cmd][] class instance to `False`. This would be useful, for example, if you wish to use something like [argparse](https://docs.python.org/3/library/argparse.html) to parse the overall command line arguments for your application:

    ```py
    from cmd2 import Cmd
    class App(Cmd):
        def __init__(self):
            super().__init__(allow_cli_args=False)
    ```

## Startup Script

You can execute commands from an initialization script by passing a file path to the
`startup_script` argument to the `cmd2.Cmd.__init__()` method like so:

```py
class StartupApp(cmd2.Cmd):
    def __init__(self):
        cmd2.Cmd.__init__(self, startup_script='.cmd2rc')
```

This text file should contain a [Command Script](./scripting.md#command-scripts). See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example for a demonstration.

You can silence a startup script's output by setting `silence_startup_script` to True:

```py
cmd2.Cmd.__init__(self, startup_script='.cmd2rc', silence_startup_script=True)
```

!!! warning

    Anything written to `stderr` will still print for a "silenced" startup script. Additionally, a startup script cannot be silenced if
    `allow_redirection` is False since silencing works by redirecting a script's output to `os.devnull`.
