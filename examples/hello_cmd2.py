#!/usr/bin/env python
# coding=utf-8
"""
This is intended to be a completely bare-bones cmd2 application suitable for rapid testing and debugging.
"""
from cmd2 import cmd2

if __name__ == '__main__':
    import sys
    # If run as the main application, simply start a bare-bones cmd2 application with only built-in functionality.

    # Set "use_ipython" to True to include the ipy command if IPython is installed, which supports advanced interactive
    # debugging of your application via introspection on self.
    app = cmd2.Cmd(use_ipython=True, persistent_history_file='cmd2_history.dat')
    app.self_in_py = True     # Enable access to "self" within the py command
    app.debug = True            # Show traceback if/when an exception occurs
    sys.exit(app.cmdloop())
