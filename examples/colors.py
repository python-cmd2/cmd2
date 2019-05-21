#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2. Demonstrating colorized output.

Experiment with the command line options on the `speak` command to see how
different output colors ca

The colors setting has three possible values:

Never
    poutput(), pfeedback(), and ppaged() strip all ANSI escape sequences
    which instruct the terminal to colorize output

Terminal
    (the default value) poutput(), pfeedback(), and ppaged() do not strip any
    ANSI escape sequences when the output is a terminal, but if the output is
    a pipe or a file the escape sequences are stripped. If you want colorized
    output you must add ANSI escape sequences, preferably using some python
    color library like `plumbum.colors`, `colorama`, `blessings`, or
    `termcolor`.

Always
    poutput(), pfeedback(), and ppaged() never strip ANSI escape sequences,
    regardless of the output destination
"""

import random
import argparse

import cmd2
from colorama import Fore, Back

FG_COLORS = {
    'black': Fore.BLACK,
    'red': Fore.RED,
    'green': Fore.GREEN,
    'yellow': Fore.YELLOW,
    'blue': Fore.BLUE,
    'magenta': Fore.MAGENTA,
    'cyan': Fore.CYAN,
    'white': Fore.WHITE,
}
BG_COLORS = {
    'black': Back.BLACK,
    'red': Back.RED,
    'green': Back.GREEN,
    'yellow': Back.YELLOW,
    'blue': Back.BLUE,
    'magenta': Back.MAGENTA,
    'cyan': Back.CYAN,
    'white': Back.WHITE,
}


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application demonstrating colorized output."""

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True
    MUMBLES = ['like', '...', 'um', 'er', 'hmmm', 'ahh']
    MUMBLE_FIRST = ['so', 'like', 'well']
    MUMBLE_LAST = ['right?']

    def __init__(self):
        shortcuts = dict(self.DEFAULT_SHORTCUTS)
        shortcuts.update({'&': 'speak'})
        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        super().__init__(use_ipython=True, multiline_commands=['orate'], shortcuts=shortcuts)

        self.maxrepeats = 3
        # Make maxrepeats settable at runtime
        self.settable['maxrepeats'] = 'max repetitions for speak command'

    speak_parser = argparse.ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    speak_parser.add_argument('-f', '--fg', choices=FG_COLORS, help='foreground color to apply to output')
    speak_parser.add_argument('-b', '--bg', choices=BG_COLORS, help='background color to apply to output')
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

        color_on = ''
        if args.fg:
            color_on += FG_COLORS[args.fg]
        if args.bg:
            color_on += BG_COLORS[args.bg]
        color_off = Fore.RESET + Back.RESET

        for i in range(min(repetitions, self.maxrepeats)):
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(color_on + ' '.join(words) + color_off)

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    mumble_parser = argparse.ArgumentParser()
    mumble_parser.add_argument('-r', '--repeat', type=int, help='how many times to repeat')
    mumble_parser.add_argument('-f', '--fg', help='foreground color to apply to output')
    mumble_parser.add_argument('-b', '--bg', help='background color to apply to output')
    mumble_parser.add_argument('words', nargs='+', help='words to say')

    @cmd2.with_argparser(mumble_parser)
    def do_mumble(self, args):
        """Mumbles what you tell me to."""
        color_on = ''
        if args.fg and args.fg in FG_COLORS:
            color_on += FG_COLORS[args.fg]
        if args.bg and args.bg in BG_COLORS:
            color_on += BG_COLORS[args.bg]
        color_off = Fore.RESET + Back.RESET

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
            self.poutput(color_on + ' '.join(output) + color_off)


if __name__ == '__main__':
    import sys
    c = CmdLineApp()
    sys.exit(c.cmdloop())
