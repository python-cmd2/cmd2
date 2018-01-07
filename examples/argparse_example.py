#!/usr/bin/env python
# coding=utf-8
"""A sample application for cmd2 showing how to use Argparse to process command line arguments for your application.
It parses command line arguments looking for known arguments, but then still passes any unknown arguments onto cmd2
to treat them as arguments at invocation.

Thanks to cmd2's built-in transcript testing capability, it also serves as a test suite for argparse_example.py when
used with the exampleSession.txt transcript.

Running `python argparse_example.py -t exampleSession.txt` will run all the commands in the transcript against
argparse_example.py, verifying that the output produced matches the transcript.
"""
import argparse
import sys

from cmd2 import Cmd, make_option, options, with_argument_parser


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
        # self.allow_cli_args = False

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
        words = []
        for word in arg:
            if opts.piglatin:
                word = '%s%say' % (word[1:], word[0])
            if opts.shout:
                arg = arg.upper()
            words.append(word)
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(' '.join(words))
            self.stdout.write('\n')
            # self.stdout.write is better than "print", because Cmd can be
            # initialized with a non-standard output destination

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input


    argparser = argparse.ArgumentParser(
      prog='sspeak',
      description='Repeats what you tell me to'
    )
    argparser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    argparser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    argparser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    argparser.add_argument('words', nargs='+', help='words to say')
    @with_argument_parser(argparser)
    def do_sspeak(self, rawarg, args=None):
        """Repeats what you tell me to."""
        words = []
        for word in args.words:
            if args.piglatin:
                word = '%s%say' % (word[1:], word[0])
            if args.shout:
                word = word.upper()
            words.append(word)
        repetitions = args.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(' '.join(words))
            self.stdout.write('\n')
            # self.stdout.write is better than "print", because Cmd can be
            # initialized with a non-standard output destination


    argparser = argparse.ArgumentParser(
      prog='tag',
      description='create an html tag, the first argument is the tag, the rest is the contents'
    )
    argparser.add_argument('tag', nargs=1, help='tag')
    argparser.add_argument('content', nargs='+', help='content to surround with tag')
    @with_argument_parser(argparser)
    def do_tag(self, cmdline, args=None):
        self.stdout.write('<{0}>{1}</{0}>'.format(args.tag[0], ' '.join(args.content)))
        self.stdout.write('\n')
        # self.stdout.write is better than "print", because Cmd can be
        # initialized with a non-standard output destination


if __name__ == '__main__':
    # You can do your custom Argparse parsing here to meet your application's needs
    parser = argparse.ArgumentParser(description='Process the arguments however you like.')

    # Add a few arguments which aren't really used, but just to get the gist
    parser.add_argument('-p', '--port', type=int, help='TCP port')
    parser.add_argument('-i', '--ip', type=str, help='IPv4 address')

    # Add an argument which enables transcript testing
    args, unknown_args = parser.parse_known_args()

    port = None
    if args.port:
        port = args.port

    ip_addr = None
    if args.ip:
        ip_addr = args.ip

    # Perform surgery on sys.argv to remove the arguments which have already been processed by argparse
    sys.argv = sys.argv[:1] + unknown_args

    # Instantiate your cmd2 application
    c = CmdLineApp()

    # And run your cmd2 application
    c.cmdloop()
