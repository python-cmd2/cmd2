#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2.

This example is very similar to example.py, but had additional
code in main() that shows how to accept a command from
the command line at invocation:

$ python cmd_as_argument.py speak -p hello there


"""

import argparse
import random

import cmd2


class CmdLineApp(cmd2.Cmd):
    """ Example cmd2 application. """

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True
    MUMBLES = ['like', '...', 'um', 'er', 'hmmm', 'ahh']
    MUMBLE_FIRST = ['so', 'like', 'well']
    MUMBLE_LAST = ['right?']

    def __init__(self):
        shortcuts = dict(cmd2.DEFAULT_SHORTCUTS)
        shortcuts.update({'&': 'speak'})
        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        super().__init__(allow_cli_args=False, use_ipython=True, multiline_commands=['orate'], shortcuts=shortcuts)

        self.self_in_py = True
        self.maxrepeats = 3
        # Make maxrepeats settable at runtime
        self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command'))

    speak_parser = argparse.ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    speak_parser.add_argument('words', nargs='+', help='words to say')

    @cmd2.with_argparser(speak_parser)
    def do_speak(self, args):
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
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(' '.join(words))

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    mumble_parser = argparse.ArgumentParser()
    mumble_parser.add_argument('-r', '--repeat', type=int, help='how many times to repeat')
    mumble_parser.add_argument('words', nargs='+', help='words to say')

    @cmd2.with_argparser(mumble_parser)
    def do_mumble(self, args):
        """Mumbles what you tell me to."""
        repetitions = args.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            output = []
            if random.random() < .33:
                output.append(random.choice(self.MUMBLE_FIRST))
            for word in args.words:
                if random.random() < .40:
                    output.append(random.choice(self.MUMBLES))
                output.append(word)
            if random.random() < .25:
                output.append(random.choice(self.MUMBLE_LAST))
            self.poutput(' '.join(output))


def main(argv=None):
    """Run when invoked from the operating system shell"""

    parser = argparse.ArgumentParser(
        description='Commands as arguments'
    )
    command_help = 'optional command to run, if no command given, enter an interactive shell'
    parser.add_argument('command', nargs='?',
                        help=command_help)
    arg_help = 'optional arguments for command'
    parser.add_argument('command_args', nargs=argparse.REMAINDER,
                        help=arg_help)

    args = parser.parse_args(argv)

    c = CmdLineApp()

    sys_exit_code = 0
    if args.command:
        # we have a command, run it and then exit
        c.onecmd_plus_hooks('{} {}'.format(args.command, ' '.join(args.command_args)))
    else:
        # we have no command, drop into interactive mode
        sys_exit_code = c.cmdloop()

    return sys_exit_code


if __name__ == '__main__':
    import sys
    sys.exit(main())
