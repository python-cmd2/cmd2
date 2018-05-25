#!/usr/bin/env python
# coding=utf-8
"""A sample application for integrating cmd2 with external event loops.

This is an example of how to use cmd2 in a way so that cmd2 doesn't own the inner event loop of your application.

This opens up the possibility of registering cmd2 input with event loops, like asyncio, without occupying the main loop.
"""
import cmd2


class Cmd2EventBased(cmd2.Cmd):
    """Basic example of how to run cmd2 without it controlling the main loop."""
    def __init__(self):
        super().__init__()

    # ... your class code here ...


if __name__ == '__main__':
    app = Cmd2EventBased()
    app.preloop()

    # Do this within whatever event loop mechanism you wish to run a single command.
    # In this case, no prompt is generated, so you need to provide one and read the user's input.
    app.onecmd_plus_hooks("help history")

    app.postloop()
