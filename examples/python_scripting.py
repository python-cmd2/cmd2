#!/usr/bin/env python
# coding=utf-8
"""A sample application for how Python scripting can provide conditional
control flow of a cmd2 application.

cmd2's built-in scripting capability, which can be invoked via the "@" shortcut
or "run_script" command, uses basic ASCII/UTF-8 text scripts and is very easy
to use.  Moreover, the trivial syntax of the script files, where there is one
command per line and the line is exactly what the user would type inside the
application, makes it so non-technical that end users can quickly learn to
create scripts.

However, there comes a time when technical end users want more capability and
power.  In particular it is common that users will want to create a script with
conditional control flow - where the next command run will depend on the
results from the previous command.  This is where the ability to run Python
scripts inside a cmd2 application via the run_pyscript command and the
"run_pyscript <script> [arguments]" syntax comes into play.

This application and the "examples/scripts/conditional.py" script serve as an
example for one way in which this can be done.
"""
import argparse
import os

import cmd2
from cmd2 import ansi


class CmdLineApp(cmd2.Cmd):
    """ Example cmd2 application to showcase conditional control flow in Python scripting within cmd2 apps."""

    def __init__(self):
        # Enable the optional ipy command if IPython is installed by setting use_ipython=True
        super().__init__(use_ipython=True)
        self._set_prompt()
        self.intro = 'Happy 𝛑 Day.  Note the full Unicode support:  😇 💩'

    def _set_prompt(self):
        """Set prompt so it displays the current working directory."""
        self.cwd = os.getcwd()
        self.prompt = ansi.style(f'{self.cwd} $ ', fg='cyan')

    def postcmd(self, stop: bool, line: str) -> bool:
        """Hook method executed just after a command dispatch is finished.

        :param stop: if True, the command has indicated the application should exit
        :param line: the command line text for this command
        :return: if this is True, the application will exit after this command and the postloop() will run
        """
        """Override this so prompt always displays cwd."""
        self._set_prompt()
        return stop

    @cmd2.with_argument_list
    def do_cd(self, arglist):
        """Change directory.
    Usage:
        cd <new_dir>
        """
        # Expect 1 argument, the directory to change to
        if not arglist or len(arglist) != 1:
            self.perror("cd requires exactly 1 argument:")
            self.do_help('cd')
            self.last_result = 'Bad arguments'
            return

        # Convert relative paths to absolute paths
        path = os.path.abspath(os.path.expanduser(arglist[0]))

        # Make sure the directory exists, is a directory, and we have read access
        err = None
        data = None
        if not os.path.isdir(path):
            err = f'{path} is not a directory'
        elif not os.access(path, os.R_OK):
            err = f'You do not have read access to {path}'
        else:
            try:
                os.chdir(path)
            except Exception as ex:
                err = f'{ex}'
            else:
                self.poutput(f'Successfully changed directory to {path}')
                data = path

        if err:
            self.perror(err)
        self.last_result = data

    # Enable tab completion for cd command
    def complete_cd(self, text, line, begidx, endidx):
        # Tab complete only directories
        return self.path_complete(text, line, begidx, endidx, path_filter=os.path.isdir)

    dir_parser = argparse.ArgumentParser()
    dir_parser.add_argument('-l', '--long', action='store_true', help="display in long format with one item per line")

    @cmd2.with_argparser(dir_parser, with_unknown_args=True)
    def do_dir(self, args, unknown):
        """List contents of current directory."""
        # No arguments for this command
        if unknown:
            self.perror("dir does not take any positional arguments:")
            self.do_help('dir')
            self.last_result = 'Bad arguments'
            return

        # Get the contents as a list
        contents = os.listdir(self.cwd)

        for f in contents:
            self.poutput(f'{f}')
        self.poutput('')

        self.last_result = contents


if __name__ == '__main__':
    import sys
    c = CmdLineApp()
    sys.exit(c.cmdloop())
