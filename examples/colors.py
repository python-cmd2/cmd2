#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2. Demonstrating colorized output.

Experiment with the command line options on the `speak` command to see how
different output colors ca

The allow_style setting has three possible values:

Never
    poutput(), pfeedback(), and ppaged() strip all ANSI style sequences
    which instruct the terminal to colorize output

Terminal
    (the default value) poutput(), pfeedback(), and ppaged() do not strip any
    ANSI style sequences when the output is a terminal, but if the output is
    a pipe or a file the style sequences are stripped. If you want colorized
    output you must add ANSI style sequences using either cmd2's internal ansi
    module or another color library such as `plumbum.colors` or `colorama`.

Always
    poutput(), pfeedback(), and ppaged() never strip ANSI style sequences,
    regardless of the output destination
"""
import argparse
from typing import Any

from colorama import Back, Fore, Style

import cmd2
from cmd2 import ansi


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application demonstrating colorized output."""
    def __init__(self):
        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        super().__init__(use_ipython=True)

        self.maxrepeats = 3
        # Make maxrepeats settable at runtime
        self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command'))

        # Should ANSI color output be allowed
        self.allow_style = ansi.STYLE_TERMINAL

    speak_parser = argparse.ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    speak_parser.add_argument('-f', '--fg', choices=ansi.fg.colors(), help='foreground color to apply to output')
    speak_parser.add_argument('-b', '--bg', choices=ansi.bg.colors(), help='background color to apply to output')
    speak_parser.add_argument('-l', '--bold', action='store_true', help='bold the output')
    speak_parser.add_argument('-u', '--underline', action='store_true', help='underline the output')
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
        output_str = ansi.style(' '.join(words), fg=args.fg, bg=args.bg, bold=args.bold, underline=args.underline)

        for _ in range(min(repetitions, self.maxrepeats)):
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(output_str)
        self.perror('error message at the end')

    @staticmethod
    def perror(msg: Any, *, end: str = '\n', apply_style: bool = True) -> None:
        """Override perror() method from `cmd2.Cmd`

        Use colorama native approach for styling the text instead of `cmd2.ansi` methods

        :param msg: message to print (anything convertible to a str with '{}'.format() is OK)
        :param end: string appended after the end of the message, default a newline
        :param apply_style: If True, then ansi.style_error will be applied to the message text. Set to False in cases
                            where the message text already has the desired style. Defaults to True.
        """
        if apply_style:
            final_msg = "{}{}{}{}".format(Fore.RED, Back.YELLOW, msg, Style.RESET_ALL)
        else:
            final_msg = "{}".format(msg)
        ansi.ansi_aware_write(sys.stderr, final_msg + end)

    def do_timetravel(self, args):
        """A command which always generates an error message, to demonstrate custom error colors"""
        self.perror('Mr. Fusion failed to start. Could not energize flux capacitor.')


if __name__ == '__main__':
    import sys
    c = CmdLineApp()
    sys.exit(c.cmdloop())
