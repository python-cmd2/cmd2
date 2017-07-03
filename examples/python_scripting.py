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
import functools
import os

from cmd2 import Cmd, options, make_option, CmdResult, set_use_arg_list


class CmdLineApp(Cmd):
    """ Example cmd2 application to showcase conditional control flow in Python scripting within cmd2 aps. """

    def __init__(self):
        # Enable the optional ipy command if IPython is installed by setting use_ipython=True
        Cmd.__init__(self, use_ipython=True)
        self._set_prompt()
        self.autorun_on_edit = False
        self.intro = 'Happy 𝛑 Day.  Note the full Unicode support:  😇  (Python 3 only)  💩'

        # For option commands, pass a list of argument strings instead of a single argument string to the do_* methods
        set_use_arg_list(True)

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

    # noinspection PyUnusedLocal
    @options([], arg_desc='<new_dir>')
    def do_cd(self, arg, opts=None):
        """Change directory."""
        # Expect 1 argument, the directory to change to
        if not arg or len(arg) != 1:
            self.perror("cd requires exactly 1 argument:", traceback_war=False)
            self.do_help('cd')
            self._last_result = CmdResult('', 'Bad arguments')
            return

        # Convert relative paths to absolute paths
        path = os.path.abspath(os.path.expanduser(arg[0]))

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
        self._last_result = CmdResult(out, err)

    # Enable directory completion for cd command by freezing an argument to path_complete() with functools.partialmethod
    complete_cd = functools.partialmethod(Cmd.path_complete, dir_only=True)

    @options([make_option('-l', '--long', action="store_true", help="display in long format with one item per line")],
             arg_desc='')
    def do_dir(self, arg, opts=None):
        """List contents of current directory."""
        # No arguments for this command
        if arg:
            self.perror("dir does not take any arguments:", traceback_war=False)
            self.do_help('dir')
            self._last_result = CmdResult('', 'Bad arguments')
            return

        # Get the contents as a list
        contents = os.listdir(self.cwd)

        fmt = '{} '
        if opts.long:
            fmt = '{}\n'
        for f in contents:
            self.stdout.write(fmt.format(f))
        self.stdout.write('\n')

        self._last_result = CmdResult(contents)


if __name__ == '__main__':
    c = CmdLineApp()
    c.cmdloop()
