# Clipboard Integration

Nearly every operating system has some notion of a short-term storage area which can be accessed by
any program. Usually this is called the :clipboard: clipboard, but sometimes people refer to it as
the paste buffer.

`cmd2` integrates with the operating system clipboard using the
[pyperclip](https://github.com/asweigart/pyperclip) module. Command output can be sent to the
clipboard by ending the command with a greater than symbol:

```text
mycommand args >
```

Think of it as redirecting the output to an unnamed, ephemeral place: the clipboard. You can also
append output to the current contents of the clipboard by ending the command with two greater than
symbols:

```text
mycommand arg1 arg2 >>
```

## Developers

You can control whether the above user features of adding output to the operating system clipboard
are allowed for the user by setting the [cmd2.Cmd.allow_clipboard][] attribute. The default value is
`True`. Set it to `False` and the above functionality will generate an error message instead of
adding the output to the clipboard. [cmd2.Cmd.allow_clipboard][] can be set upon initialization, and
you can change it at any time from within your code.

If you would like your `cmd2` based application to be able to use the clipboard in additional or
alternative ways, you can use the following methods (which work uniformly on Windows, macOS, and
Linux).

::: cmd2.clipboard
