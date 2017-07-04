#!/usr/bin/env python
# coding=utf-8
"""A sample application for cmd2 showing how to use Argparse to process command line arguments for your application.
It doubles as an example of how you can still do transcript testing even if allow_cli_args is false.

Thanks to cmd2's built-in transcript testing capability, it also serves as a test suite for argparse_example.py when
used with the exampleSession.txt transcript.

Running `python argparse_example.py -t exampleSession.txt` will run all the commands in the transcript against
argparse_example.py, verifying that the output produced matches the transcript.
"""
import argparse

from cmd2 import Cmd, make_option, options


class CmdLineApp(Cmd):
    """ Example cmd2 application. """
    def __init__(self, ip_addr=None, port=None, transcript_files=None):
        self.multilineCommands = ['orate']
        self.shortcuts.update({'&': 'speak'})
        self.maxrepeats = 3

        # Add stuff to settable and/or shortcuts before calling base class initializer
        self.settable['maxrepeats'] = 'Max number of `--repeat`s allowed'

        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        Cmd.__init__(self, use_ipython=False, transcript_files=transcript_files)

        # Disable cmd's usage of command-line arguments as commands to be run at invocation
        self.allow_cli_args = False

        # Example of args set from the command-line (but they aren't being used here)
        self._ip = ip_addr
        self._port = port

        # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
        # self.default_to_shell = True

    @options([make_option('-p', '--piglatin', action="store_true", help="atinLay"),
              make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
              make_option('-r', '--repeat', type="int", help="output [n] times")
              ])
    def do_speak(self, arg, opts=None):
        """Repeats what you tell me to."""
        arg = ''.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:], arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(arg)
            self.stdout.write('\n')
            # self.stdout.write is better than "print", because Cmd can be
            # initialized with a non-standard output destination

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input


if __name__ == '__main__':
    # You can do your custom Argparse parsing here to meet your application's needs
    parser = argparse.ArgumentParser(description='Process the arguments however you like.')

    # Add a few arguments which aren't really used, but just to get the gist
    parser.add_argument('-p', '--port', type=int, help='TCP port')
    parser.add_argument('-i', '--ip', type=str, help='IPv4 address')

    # Add an argument which enables transcript testing
    parser.add_argument('-t', '--test', type=str, help='Test against transcript in FILE (wildcards OK)')
    args = parser.parse_args()

    port = None
    if args.port:
        port = args.port

    ip_addr = None
    if args.ip:
        ip_addr = args.ip

    transcripts = None
    if args.test:
        transcripts = [args.test]

    # Instantiate your cmd2 application
    c = CmdLineApp(transcript_files=transcripts)

    # And run your cmd2 application
    c.cmdloop()
