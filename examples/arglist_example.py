#!/usr/bin/env python
# coding=utf-8
"""A sample application for cmd2 showing how to use argparse to
process command line arguments for your application.

Thanks to cmd2's built-in transcript testing capability, it also
serves as a test suite for argparse_example.py when used with the
exampleSession.txt transcript.

Running `python argparse_example.py -t exampleSession.txt` will run
all the commands in the transcript against argparse_example.py,
verifying that the output produced matches the transcript.
"""
import argparse
import sys

from cmd2 import Cmd, make_option, options, with_argument_parser, with_argument_list


class CmdLineApp(Cmd):
    """ Example cmd2 application. """
    def __init__(self):
        self.use_argument_list = True
        Cmd.__init__(self)

    def do_tag(self, arglist):
        """verion of creating an html tag using arglist instead of argparser"""
        if len(arglist) >= 2:
            tag = arglist[0]
            content = arglist[1:]
            self.poutput('<{0}>{1}</{0}>'.format(tag, ' '.join(content)))
        else:
            self.perror("tag requires at least 2 arguments")

if __name__ == '__main__':
    # Instantiate your cmd2 application
    c = CmdLineApp()

    # And run your cmd2 application
    c.cmdloop()
