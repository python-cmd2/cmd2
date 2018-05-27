#!/usr/bin/env python
# coding=utf-8
from cmd2 import cmd2

if __name__ == '__main__':
    # If run as the main application, simply start a bare-bones cmd2 application with only built-in functionality.

    # Set "use_ipython" to True to include the ipy command if IPython is installed, which supports advanced interactive
    # debugging of your application via introspection on self.
    app = cmd2.Cmd(use_ipython=True)
    app.locals_in_py = True
    app.cmdloop()
