# Prompt

`cmd2` issues a configurable prompt before soliciting user input.

## Customizing the Prompt

This prompt can be configured by setting the [cmd2.Cmd.prompt][] instance attribute. This contains
the string which should be printed as a prompt for user input. See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example for the simple use case of statically setting the prompt.

## Continuation Prompt

When a user types a [Multiline Command](./multiline_commands.md) it may span more than one line of
input. The prompt for the first line of input is specified by the `cmd2.Cmd.prompt` instance
attribute. The prompt for subsequent lines of input is defined by the `cmd2.Cmd.continuation_prompt`
attribute. See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example for a demonstration of customizing the continuation prompt.

## Updating the prompt

If you wish to update the prompt between commands, you can do so using one of the
[Application Lifecycle Hooks](./hooks.md#application-lifecycle-hooks) such as a
[Postcommand hook](./hooks.md#postcommand-hooks). See
[python_scripting.py](https://github.com/python-cmd2/cmd2/blob/main/examples/python_scripting.py)
for an example of dynamically updating the prompt.

## Asynchronous Feedback

`cmd2` provides a function to deliver asynchronous feedback to the user without interfering with the
command line. This allows feedback to be provided while the user is still entering text at the
prompt.

- [cmd2.Cmd.add_alert][]

### Asynchronous Feedback Mechanisms

Alerts can interact with the CLI in two ways:

1. **Message Printing**: It can print a message directly above the current prompt line.
1. **Prompt Updates**: It can dynamically replace the text of the active prompt to reflect changing
   state.

!!! note

    To ensure the user interface remains accurate, a prompt update is ignored if the alert
    was created before the current prompt was rendered. This prevents older alerts from overwriting a newer
    prompt, though the alert's message will still be printed.

### Terminal Window Management

`cmd2` also provides a function to change the title of the terminal window.

- [cmd2.Cmd.set_window_title][]

The easiest way to understand these functions is to see the
[async_printing.py](https://github.com/python-cmd2/cmd2/blob/main/examples/async_printing.py)
example for a demonstration.

## Bottom Toolbar

`cmd2` supports an optional, persistent bottom toolbar that is always visible at the bottom of the
terminal window while the application is waiting for input and while commands execute. Command
output appears above the toolbar.

### Enabling the Toolbar

To enable the toolbar, set `enable_bottom_toolbar=True` in the [cmd2.Cmd.__init__][] constructor:

```py
class App(cmd2.Cmd):
    def __init__(self):
        super().__init__(enable_bottom_toolbar=True)
```

### Customizing Toolbar Content

You can customize the content of the toolbar by overriding the [cmd2.Cmd.get_bottom_toolbar][]
method.

```py
from prompt_toolkit.formatted_text import AnyFormattedText


def get_bottom_toolbar(self) -> AnyFormattedText:
    return [
        ("ansigreen", "My Application Name"),
        ("", " - "),
        ("ansiyellow", "Current Status: Idle"),
    ]
```

### Refreshing the Toolbar

The toolbar is rendered by `prompt-toolkit` and is naturally redrawn whenever the prompt is
refreshed. If you want the toolbar to update automatically during input and command execution (for
example, to display a clock), you can set `refresh_interval` in the [cmd2.Cmd.__init__][]
constructor to a value greater than 0.0.

```py
class App(cmd2.Cmd):
    def __init__(self):
        super().__init__(refresh_interval=0.5)
```

See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example for a demonstration of this technique. Run its `work 5` command to see the clock update
while the command prints output.

Inside the command loop, `get_bottom_toolbar()` runs in a background UI thread, at the prompt as
well as during command execution, because a single prompt-toolkit application renders both. Keep the
callback fast and use a lock when reading state that a command or another thread modifies.

### Commands That Take Over the Terminal

While the toolbar is running, `ppaged()` uses an embedded pager which keeps the same toolbar visible
and refreshing instead of handing the terminal to an external pager. Short output is printed
directly above the toolbar, and longer output becomes a scrollable, searchable view. Set
`self.use_builtin_pager = False` to opt out and use your configured external `pager`/`pager_chop`
commands. See [Embedded pager](./os.md#embedded-pager) for the key bindings and full details.

cmd2 temporarily hides the toolbar for its input prompts, external pagers, Python environments, and
shell commands. It also hides it while a command's output is piped to another process, since that
process may be interactive, as `less` and `fzf` are. It restores the toolbar when those operations
finish.

For custom terminal UIs, calls to `input()`, or subprocesses your own command code starts, use
[cmd2.Cmd.suspend_bottom_toolbar][]:

```py
with self.suspend_bottom_toolbar():
    answer = input("Continue? ")
```

Suspending matters for subprocesses even when they only print. While the toolbar is displayed, the
terminal is in raw mode, so the kernel generates no signals from keystrokes. cmd2 sends `Ctrl-C` on
to its own process group, which reaches a subprocess your command started and waits on, but `Ctrl-\`
(`SIGQUIT`) does nothing, exactly as at the main prompt.

The command toolbar is used by the interactive command loop, including startup commands and scripts
launched from that loop. It is disabled for non-interactive input. Calls to `onecmd_plus_hooks()`
outside the command loop do not start a toolbar.
