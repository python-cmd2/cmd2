#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2. Demonstrating colorized output using the plumbum package.

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

WARNING: This example requires the plumbum package, which isn't normally required by cmd2.
"""
import argparse

import cmd2
from cmd2 import ansi
from plumbum.colors import bg, fg


class FgColors(ansi.ColorBase):
    black = fg.Black
    red = fg.DarkRedA
    green = fg.MediumSpringGreen
    yellow = fg.LightYellow
    blue = fg.RoyalBlue1
    magenta = fg.Purple
    cyan = fg.SkyBlue1
    white = fg.White
    purple = fg.Purple


class BgColors(ansi.ColorBase):
    black = bg.BLACK
    red = bg.DarkRedA
    green = bg.MediumSpringGreen
    yellow = bg.LightYellow
    blue = bg.RoyalBlue1
    magenta = bg.Purple
    cyan = bg.SkyBlue1
    white = bg.White
    purple = bg.Purple


def get_fg(name: str):
    return str(FgColors[name])


def get_bg(name: str):
    return str(BgColors[name])


ansi.fg_lookup = get_fg
ansi.bg_lookup = get_bg


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
    speak_parser.add_argument('-f', '--fg', choices=FgColors.colors(), help='foreground color to apply to output')
    speak_parser.add_argument('-b', '--bg', choices=BgColors.colors(), help='background color to apply to output')
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


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
