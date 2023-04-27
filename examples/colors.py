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
    output, add ANSI style sequences using cmd2's internal ansi module.

Always
    poutput(), pfeedback(), and ppaged() never strip ANSI style sequences,
    regardless of the output destination
"""

import cmd2
from cmd2 import (
    Bg,
    Fg,
    ansi,
)

fg_choices = [c.name.lower() for c in Fg]
bg_choices = [c.name.lower() for c in Bg]


class CmdLineApp(cmd2.Cmd):
    """Example cmd2 application demonstrating colorized output."""

    def __init__(self):
        # Set include_ipy to True to enable the "ipy" command which runs an interactive IPython shell
        super().__init__(include_ipy=True)

        self.maxrepeats = 3
        # Make maxrepeats settable at runtime
        self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command', self))

        # Should ANSI color output be allowed
        self.allow_style = ansi.AllowStyle.TERMINAL

    speak_parser = cmd2.Cmd2ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    speak_parser.add_argument('-f', '--fg', choices=fg_choices, help='foreground color to apply to output')
    speak_parser.add_argument('-b', '--bg', choices=bg_choices, help='background color to apply to output')
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

        fg_color = Fg[args.fg.upper()] if args.fg else None
        bg_color = Bg[args.bg.upper()] if args.bg else None
        output_str = ansi.style(' '.join(words), fg=fg_color, bg=bg_color, bold=args.bold, underline=args.underline)

        for _ in range(min(repetitions, self.maxrepeats)):
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(output_str, apply_style=False)

    def do_timetravel(self, _):
        """A command which always generates an error message, to demonstrate custom error colors"""
        self.perror('Mr. Fusion failed to start. Could not energize flux capacitor.')


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
