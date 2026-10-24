# Embedding in Textual

[Textual](https://textual.textualize.io/) builds full-screen terminal user interfaces with widgets,
layouts, and mouse support, while `cmd2` builds interactive command interpreters. You don't have to
choose between them. [textual-tty](https://github.com/ttygroup/textual-tty) provides a `Terminal`
widget for Textual applications, which is a terminal emulator that runs a program attached to a
pseudo-terminal. That program can be a `cmd2` application, so a Textual application can show a
`cmd2` application in one pane and, beside it, other widgets which display realtime status and
situational awareness information. This can be much richer than what fits in a
[bottom toolbar](../features/prompt.md#bottom-toolbar).

The
[textual_tty_embed.py](https://github.com/python-cmd2/cmd2/blob/main/examples/textual_tty_embed.py)
example shows how to do this. It has a `cmd2` application in a terminal pane on the left. On the
right, a status panel shows whether the `cmd2` application is idle or running a command, how many
commands it has run, and how long the last one took, and a clock is updated by Textual on its own.

!!! warning

    textual-tty is still pre-alpha software, so its API may change. The example was written for
    textual-tty 0.4. Also, on Windows textual-tty can only start a program by name and can't pass
    it arguments, so the example's Textual application requires a POSIX system such as Linux or
    macOS.

## Running the Example

Neither Textual nor textual-tty are dependencies of `cmd2`. In a `cmd2` checkout, textual-tty is
part of the development environment on POSIX systems, so you can run:

```shell
uv run examples/textual_tty_embed.py
```

Otherwise, install textual-tty, which also installs Textual, into your own environment:

```shell
pip install textual-tty
python examples/textual_tty_embed.py
```

Use the `quit` command or press ++ctrl+q++ to exit. Pass `--cmd2-only` to run just the `cmd2`
application in your current terminal, without Textual.

## How It Works

The Textual application runs the `cmd2` application as a child process in a `Terminal` widget. The
child process is the example script itself, run with `--cmd2-only --report-status`:

```py
def compose(self) -> ComposeResult:
    yield Header()
    with Horizontal():
        with Vertical(id="cmd2-pane"):
            yield Terminal(command=[sys.executable, __file__, "--cmd2-only", "--report-status"], id="cmd2")
        with Vertical(id="sidebar"):
            yield StatusPanel(id="status")
            yield ClockPanel(id="clock")
    yield Footer()
```

Because it is attached to a pseudo-terminal, the `cmd2` application is a completely normal `cmd2`
application which uses `prompt-toolkit` and doesn't know that it is embedded. Everything typed into
the focused `Terminal` goes to the `cmd2` application.

To report its state, the `cmd2` application registers a
[postparsing hook](../features/hooks.md#postparsing-hooks), which runs before each command, and a
[command finalization hook](../features/hooks.md#command-finalization-hooks), which runs after it.
Both of them call [cmd2.Cmd.set_window_title][] with a JSON document. The document is prefixed with
`cmd2-status:` so that the Textual application can tell it apart from other window titles. The
`Terminal` widget turns each title change into a `Terminal.TitleChanged` message, which the Textual
application handles to update the status panel:

```py
def on_terminal_title_changed(self, event: Terminal.TitleChanged) -> None:
    if not event.title.startswith(STATUS_PREFIX):
        return
    with contextlib.suppress(TypeError, ValueError, OverflowError, RecursionError):
        status = json.loads(event.title.removeprefix(STATUS_PREFIX))
        if isinstance(status, dict):
            self.query_one(StatusPanel).apply(status)
```

Since the status travels through the pseudo-terminal, there are no sockets, files, or threads to
manage.

## Things to Watch Out For

The example handles several details which are easy to miss when building something similar:

- Command finalization hooks run for every line of input, including blank lines, comments,
  ++ctrl+c++ at the prompt, and lines with syntax errors. The other hooks only run for lines which
  were parsed into a statement, so check whether `data.statement` is `None` in a finalization hook.
- Commands run by other commands, like `run_script`, `history -r`, and `run_pyscript`, go through
  the hooks too. The example counts the running commands so that only the outermost one is reported.
- The postparsing hooks stop running as soon as one of them sets `stop` or raises an exception, but
  the finalization hooks still run. If your application has other postparsing hooks, register the
  one which counts commands first so that it is never skipped.
- `prompt-toolkit` buffers its output, so flush it after setting the window title when a command
  starts. Otherwise the "running" state only reaches the Textual application after the command is
  done.
- Any program run in the terminal, for example by the `shell` command, can set the window title.
  Validate a status document before using it. Besides `json.JSONDecodeError`, `json.loads` raises
  `ValueError` for integers with too many digits and `RecursionError` for documents which are nested
  too deeply. Also escape the document's strings with `textual.markup.escape` before putting them in
  Textual markup.
- Only report status through the window title when running inside the Textual application. In a
  normal terminal, it would overwrite the title of the user's window.
- When the child process exits, `Terminal.ProcessExited.exit_code` holds its exit code, which is the
  negated signal number if a signal killed it. The example passes the exit code back to the shell,
  using 128 plus the signal number like a shell does, and when it isn't 0 the example keeps the
  terminal on the screen so that any traceback can still be read.
- A `Terminal` sizes its pseudo-terminal from its outer size, so put a border on a container around
  the `Terminal` rather than on the `Terminal` itself. Otherwise the `cmd2` application draws more
  rows than are visible and its prompt can end up hidden.
- The focused `Terminal` sends almost every key press to the `cmd2` application. Textual's built-in
  ++ctrl+q++ binding to quit is a priority binding, so it still works.
