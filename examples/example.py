#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd2.

Thanks to cmd2's built-in transcript testing capability, it also serves as a
test suite for example.py when used with the exampleSession.txt transcript.

Running `python example.py -t exampleSession.txt` will run all the commands in
the transcript against example.py, verifying that the output produced matches
the transcript.
"""

import random

from cmd2 import Cmd, make_option, options, set_use_arg_list


class CmdLineApp(Cmd):
    """ Example cmd2 application. """

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True
    MUMBLES = ['like', '...', 'um', 'er', 'hmmm', 'ahh']
    MUMBLE_FIRST = ['so', 'like', 'well']
    MUMBLE_LAST = ['right?']

    def __init__(self):
        self.abbrev = True
        self.multilineCommands = ['orate']
        self.maxrepeats = 3

        # Add stuff to settable and shortcuts before calling base class initializer
        self.settable['maxrepeats'] = 'max repetitions for speak command'
        self.shortcuts.update({'&': 'speak'})

        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        Cmd.__init__(self, use_ipython=False)

        # For option commands, pass a single argument string instead of a list of argument strings to the do_* methods
        set_use_arg_list(False)

    opts = [make_option('-p', '--piglatin', action="store_true", help="atinLay"),
            make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
            make_option('-r', '--repeat', type="int", help="output [n] times")]

    @options(opts, arg_desc='(text to say)')
    def do_speak(self, arg, opts=None):
        """Repeats what you tell me to."""
        arg = ''.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:], arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.poutput(arg)
            # recommend using the poutput function instead of
            # self.stdout.write or "print", because Cmd allows the user
            # to redirect output

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    @options([ make_option('-r', '--repeat', type="int", help="output [n] times") ])
    def do_mumble(self, arg, opts=None):
        """Mumbles what you tell me to."""
        repetitions = opts.repeat or 1
        arg = arg.split()
        for i in range(min(repetitions, self.maxrepeats)):
            output = []
            if (random.random() < .33):
                output.append(random.choice(self.MUMBLE_FIRST))
            for word in arg:
                if (random.random() < .40):
                    output.append(random.choice(self.MUMBLES))
                output.append(word)
            if (random.random() < .25):
                output.append(random.choice(self.MUMBLE_LAST))
            self.poutput(' '.join(output))

if __name__ == '__main__':
    c = CmdLineApp()
    c.cmdloop()
