#!/usr/bin/env python
# coding=utf-8
"""A sample application for how Python scripting can provide conditional control flow of a cmd2 application.

cmd2's built-in scripting capability which can be invoked via the "@" shortcut or "load" command and uses basic ASCII
text scripts is very easy to use.  Moreover, the trivial syntax of the script files where there is one command per line
and the line is exactly what the user would type inside the application makes it so non-technical end users can quickly
learn to create scripts.

However, there comes a time when technical end users want more capability and power.  In particular it is common that
users will want to create a script with conditional control flow - where the next command run will depend on the results
from the previous command.  This is where the ability to run Python scripts inside a cmd2 application via the pyscript
command and the "pyscript <script> [arguments]" syntax comes into play.

This application and the "scripts/conditional.py" script serve as an example for one way in which this can be done.
"""
import argparse
import os

import cmd2


class CmdLineApp(cmd2.Cmd):
    """ Example cmd2 application to showcase conditional control flow in Python scripting within cmd2 aps. """

    def __init__(self):
        # Enable the optional ipy command if IPython is installed by setting use_ipython=True
        super().__init__(use_ipython=True)
        self._set_prompt()
        self.intro = 'Happy 𝛑 Day.  Note the full Unicode support:  😇  (Python 3 only)  💩'
        self.locals_in_py = True

    def _set_prompt(self):
        """Set prompt so it displays the current working directory."""
        self.cwd = os.getcwd()
        self.prompt = self.colorize('{!r} $ '.format(self.cwd), 'cyan')

    def postcmd(self, stop, line):
        """Hook method executed just after a command dispatch is finished.

        :param stop: bool - if True, the command has indicated the application should exit
        :param line: str - the command line text for this command
        :return: bool - if this is True, the application will exit after this command and the postloop() will run
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
            self.perror("cd requires exactly 1 argument:", traceback_war=False)
            self.do_help('cd')
            self._last_result = cmd2.CmdResult('', 'Bad arguments')
            return

        # Convert relative paths to absolute paths
        path = os.path.abspath(os.path.expanduser(arglist[0]))

        # Make sure the directory exists, is a directory, and we have read access
        out = ''
        err = ''
        if not os.path.isdir(path):
            err = '{!r} is not a directory'.format(path)
        elif not os.access(path, os.R_OK):
            err = 'You do not have read access to {!r}'.format(path)
        else:
            try:
                os.chdir(path)
            except Exception as ex:
                err = '{}'.format(ex)
            else:
                out = 'Successfully changed directory to {!r}\n'.format(path)
                self.stdout.write(out)

        if err:
            self.perror(err, traceback_war=False)
        self._last_result = cmd2.CmdResult(out, err)

    # Enable tab completion for cd command
    def complete_cd(self, text, line, begidx, endidx):
        return self.path_complete(text, line, begidx, endidx, dir_only=True)

    dir_parser = argparse.ArgumentParser()
    dir_parser.add_argument('-l', '--long', action='store_true', help="display in long format with one item per line")

    @cmd2.with_argparser_and_unknown_args(dir_parser)
    def do_dir(self, args, unknown):
        """List contents of current directory."""
        # No arguments for this command
        if unknown:
            self.perror("dir does not take any positional arguments:", traceback_war=False)
            self.do_help('dir')
            self._last_result = cmd2.CmdResult('', 'Bad arguments')
            return

        # Get the contents as a list
        contents = os.listdir(self.cwd)

        fmt = '{} '
        if args.long:
            fmt = '{}\n'
        for f in contents:
            self.stdout.write(fmt.format(f))
        self.stdout.write('\n')

        self._last_result = cmd2.CmdResult(contents)


if __name__ == '__main__':
    c = CmdLineApp()
    c.cmdloop()
