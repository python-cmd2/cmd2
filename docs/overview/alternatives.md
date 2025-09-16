# Alternatives

For programs that do not interact with the user in a continuous loop - programs that simply accept a
set of arguments from the command line, return results, and do not keep the user within the
program's environment - all you need are [sys](https://docs.python.org/3/library/sys.html).argv (the
command-line arguments) and [argparse](https://docs.python.org/3/library/argparse.html) (for parsing
UNIX-style options and flags). Though some people may prefer
[docopt](https://pypi.org/project/docopt) or [click](https://click.palletsprojects.com) to
[argparse](https://docs.python.org/3/library/argparse.html).

The [textual](https://textual.textualize.io/) module is capable of building sophisticated
full-screen terminal user interfaces (TUIs) that are not limited to simple text input and output;
they can paint the screen with options that are selected from using the cursor keys and even mouse
clicks. However, programming a `textual` application is not as straightforward as using `cmd2`.

Several Python packages exist for building interactive command-line applications approximately
similar in concept to [cmd](https://docs.python.org/3/library/cmd.html) applications. None of them
share `cmd2`'s close ties to [cmd](https://docs.python.org/3/library/cmd.html), but they may be
worth investigating nonetheless. Two of the most mature and full-featured are:

- [Python Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)
- [Click](https://click.palletsprojects.com)

[Python Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) is a library for
building powerful interactive command lines and terminal applications in Python. It provides a lot
of advanced visual features like syntax highlighting, bottom bars, and the ability to create
fullscreen apps.

[Click](https://click.palletsprojects.com) is a Python package for creating beautiful command line
interfaces in a composable way with as little code as necessary. It is more geared towards command
line utilities instead of command line interpreters, but it can be used for either.

Getting a working command-interpreter application based on either
[Python Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit) or
[Click](https://click.palletsprojects.com) requires a good deal more effort and boilerplate code
than `cmd2`. `cmd2` focuses on providing an excellent out-of-the-box experience with as many useful
features as possible built in for free with as little work required on the developer's part as
possible. We believe that `cmd2` provides developers the easiest way to write a command-line
interpreter, while allowing a good experience for end users.

If you are seeking a visually richer end-user experience and don't mind investing more development
time, we would recommend checking out [Textual](https://github.com/Textualize/textual) as this can
be used to build very sophisticated user interfaces in a terminal that are more akin to feature-rich
web GUIs.
