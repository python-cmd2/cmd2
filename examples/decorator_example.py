#!/usr/bin/env python
# coding=utf-8
"""A sample application showing how to use cmd2's argparse decorators to
process command line arguments for your application.

Thanks to cmd2's built-in transcript testing capability, it also
serves as a test suite when used with the exampleSession.txt transcript.

Running `python decorator_example.py -t exampleSession.txt` will run
all the commands in the transcript against decorator_example.py,
verifying that the output produced matches the transcript.
"""
import argparse
from typing import List

import cmd2


class CmdLineApp(cmd2.Cmd):
    """ Example cmd2 application. """
    def __init__(self, ip_addr=None, port=None, transcript_files=None):
        shortcuts = dict(cmd2.DEFAULT_SHORTCUTS)
        shortcuts.update({'&': 'speak'})
        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        super().__init__(use_ipython=False, transcript_files=transcript_files, multiline_commands=['orate'],
                         shortcuts=shortcuts)

        self.maxrepeats = 3
        # Make maxrepeats settable at runtime
        self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command'))

        # Example of args set from the command-line (but they aren't being used here)
        self._ip = ip_addr
        self._port = port

        # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
        # self.default_to_shell = True

    speak_parser = argparse.ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    speak_parser.add_argument('words', nargs='+', help='words to say')

    @cmd2.with_argparser(speak_parser)
    def do_speak(self, args: argparse.Namespace):
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
            self.poutput(' '.join(words))

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    tag_parser = argparse.ArgumentParser()
    tag_parser.add_argument('tag', help='tag')
    tag_parser.add_argument('content', nargs='+', help='content to surround with tag')

    @cmd2.with_argparser(tag_parser)
    def do_tag(self, args: argparse.Namespace):
        """create an html tag"""
        # The Namespace always includes the Statement object created when parsing the command line
        statement = args.__statement__

        self.poutput("The command line you ran was: {}".format(statement.command_and_args))
        self.poutput("It generated this tag:")
        self.poutput('<{0}>{1}</{0}>'.format(args.tag, ' '.join(args.content)))

    @cmd2.with_argument_list
    def do_tagg(self, arglist: List[str]):
        """version of creating an html tag using arglist instead of argparser"""
        if len(arglist) >= 2:
            tag = arglist[0]
            content = arglist[1:]
            self.poutput('<{0}>{1}</{0}>'.format(tag, ' '.join(content)))
        else:
            self.perror("tagg requires at least 2 arguments")


if __name__ == '__main__':
    import sys

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
    sys.exit(c.cmdloop())
