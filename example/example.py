#!/usr/bin/env python
# coding=utf-8
"""A sample application for cmd2.

Thanks to cmd2's built-in transtript testing capability, it also serves as a test suite for example.py when used with
 the exampleSession.txt transcript.

Running `python example.py -t exampleSession.txt` will run all the commands in the transcript against example.py,
verifying that the output produced matches the transcript.
"""

from cmd2 import Cmd, make_option, options


class CmdLineApp(Cmd):
    """ Example cmd2 application. """
    multilineCommands = ['orate']
    Cmd.shortcuts.update({'&': 'speak'})
    maxrepeats = 3
    Cmd.settable.append('maxrepeats')

    # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
    # default_to_shell = True

    def __init__(self):
        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        Cmd.__init__(self, use_ipython=False)

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
    c = CmdLineApp()
    c.cmdloop()
