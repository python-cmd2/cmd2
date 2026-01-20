#!/usr/bin/env python
"""This is intended to be a completely bare-bones cmd2 application suitable for rapid testing and debugging."""

from prompt_toolkit.shortcuts import CompleteStyle

from cmd2 import (
    cmd2,
)

if __name__ == '__main__':
    import sys

    # If run as the main application, simply start a bare-bones cmd2 application with only built-in functionality.
    app = cmd2.Cmd(
        complete_style=CompleteStyle.READLINE_LIKE,  # Use readline style tab completion instead of prompt-toolkit style
        include_ipy=True,  # Enable support for interactive Python shell via py command
        include_py=True,  # Enable support for interactive IPython shell via ipy command
        persistent_history_file='cmd2_history.dat',  # Persist history between runs
    )
    app.self_in_py = True  # Enable access to "self" within the py command
    app.debug = True  # Show traceback if/when an exception occurs
    sys.exit(app.cmdloop())
