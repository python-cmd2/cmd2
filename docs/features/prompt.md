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

`cmd2` provides these functions to provide asynchronous feedback to the user without interfering
with the command line. This means the feedback is provided to the user when they are still entering
text at the prompt. To use this functionality, the application must be running in a terminal that
supports [VT100](https://en.wikipedia.org/wiki/VT100) control characters. Linux, Mac, and Windows 10
and greater all support these.

- [cmd2.Cmd.async_alert][]
- [cmd2.Cmd.async_update_prompt][]
- [cmd2.Cmd.async_refresh_prompt][]
- [cmd2.Cmd.need_prompt_refresh][]

`cmd2` also provides a function to change the title of the terminal window. This feature requires
the application be running in a terminal that supports VT100 control characters. Linux, Mac, and
Windows 10 and greater all support these.

- [cmd2.Cmd.set_window_title][]

The easiest way to understand these functions is to see the
[async_printing.py](https://github.com/python-cmd2/cmd2/blob/main/examples/async_printing.py)
example for a demonstration.

## Bottom Toolbar

`cmd2` supports an optional, persistent bottom toolbar that is always visible at the bottom of the
terminal window while the application is idle and waiting for input.

### Enabling the Toolbar

To enable the toolbar, set `bottom_toolbar=True` in the [cmd2.Cmd.__init__][] constructor:

```py
class App(cmd2.Cmd):
    def __init__(self):
        super().__init__(bottom_toolbar=True)
```

### Customizing Toolbar Content

You can customize the content of the toolbar by overriding the [cmd2.Cmd.get_bottom_toolbar][]
method. This method should return either a string or a list of `(style, text)` tuples for formatted
text.

```py
    def get_bottom_toolbar(self) -> list[str | tuple[str, str]] | None:
        return [
            ('ansigreen', 'My Application Name'),
            ('', ' - '),
            ('ansiyellow', 'Current Status: Idle'),
        ]
```

### Refreshing the Toolbar

Since the toolbar is rendered by `prompt-toolkit` as part of the prompt, it is naturally redrawn
whenever the prompt is refreshed. If you want the toolbar to update automatically (for example, to
display a clock), you can use a background thread to call `app.invalidate()` periodically.

See the
[getting_started.py](https://github.com/python-cmd2/cmd2/blob/main/examples/getting_started.py)
example for a demonstration of this technique.
