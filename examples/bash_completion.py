#!/usr/bin/env python3
# coding=utf-8
# PYTHON_ARGCOMPLETE_OK - This is required at the beginning of the file to enable argcomplete support
"""A simple example demonstrating integration with argcomplete.

This example demonstrates how to achieve automatic auto-completion of argparse arguments for a command-line utility
(CLU) in the Bash shell.

Realistically it will probably only work on Linux and then only in a Bash shell.  With some effort you can probably get
it to work on macOS or Windows Subsystem for Linux (WSL); but then again, specifically within a Bash shell.  This
automatic Bash completion integration with the argcomplete module is included within cmd2 in order to assist developers
with providing a the best possible out-of-the-box experience with their cmd2 applications, which in many cases will
accept argparse arguments on the command-line when executed.  But from an architectural point of view, the
"argcomplete_bridge" functionality within cmd2 doesn't really depend on the rest of cmd2 and could be used in your own
CLU which doesn't use cmd2.

WARNING:  For this example to work correctly you need the argcomplete module installed and activated:
    pip install argcomplete
    activate-global-python-argcomplete
Please see https://github.com/kislyuk/argcomplete for more information on argcomplete.
"""
import argparse

optional_strs = ['Apple', 'Banana', 'Cranberry', 'Durian', 'Elderberry']

bash_parser = argparse.ArgumentParser(prog='base')

bash_parser.add_argument('option', choices=['load', 'export', 'reload'])

bash_parser.add_argument('-u', '--user', help='User name')
bash_parser.add_argument('-p', '--passwd', help='Password')

input_file = bash_parser.add_argument('-f', '--file', type=str, help='Input File')

if __name__ == '__main__':
    from cmd2.argcomplete_bridge import bash_complete
    # bash_complete flags this argument telling AutoCompleter to yield to bash to perform
    # tab completion of a file path
    bash_complete(input_file)

flag_opt = bash_parser.add_argument('-o', '--optional', help='Optional flag with choices')
setattr(flag_opt, 'arg_choices', optional_strs)

# Handle bash completion if it's installed
# This early check allows the script to bail out early to provide tab-completion results
# to the argcomplete library. Putting this at the end of the file would cause the full application
# to load fulfill every tab-completion request coming from bash.  This can cause a notable delay
# on the bash prompt.
try:
    # only move forward if we can import CompletionFinder and AutoCompleter
    from cmd2.argcomplete_bridge import CompletionFinder
    from cmd2.argparse_completer import AutoCompleter
    import sys
    if __name__ == '__main__':
        completer = CompletionFinder()

        # completer will return results to argcomplete and exit the script
        completer(bash_parser, AutoCompleter(bash_parser))
except ImportError:
    pass

# Intentionally below the bash completion code to reduce tab completion lag
import cmd2


class DummyApp(cmd2.Cmd):
    """
    Dummy cmd2 app
    """

    def __init__(self):
        super().__init__()


if __name__ == '__main__':
    args = bash_parser.parse_args()

    # demonstrates some handling of the command line parameters

    if args.user is None:
        user = input('Username: ')
    else:
        user = args.user

    if args.passwd is None:
        import getpass
        password = getpass.getpass()
    else:
        password = args.passwd

    if args.file is not None:
        print('Loading file: {}'.format(args.file))

    # Clear the argumentns so cmd2 doesn't try to parse them
    sys.argv = sys.argv[:1]

    app = DummyApp()
    app.cmdloop()
