#!/usr/bin/env python
# coding=utf-8
"""
A sample application for cmd which can be used to show how to migrate to cmd2.
"""
import cmd
import random


class CmdLineApp(cmd.Cmd):
    """ Example cmd application. """

    MUMBLES = ['like', '...', 'um', 'er', 'hmmm', 'ahh']
    MUMBLE_FIRST = ['so', 'like', 'well']
    MUMBLE_LAST = ['right?']

    def do_exit(self, line):
        """Exit the application"""
        return True

    do_EOF = do_exit
    do_quit = do_exit

    def do_speak(self, line):
        """Repeats what you tell me to."""
        print(line, file=self.stdout)

    do_say = do_speak

    def do_mumble(self, line):
        """Mumbles what you tell me to."""
        words = line.split(' ')
        output = []
        if random.random() < .33:
            output.append(random.choice(self.MUMBLE_FIRST))
        for word in words:
            if random.random() < .40:
                output.append(random.choice(self.MUMBLES))
            output.append(word)
        if random.random() < .25:
            output.append(random.choice(self.MUMBLE_LAST))
        print(' '.join(output), file=self.stdout)


if __name__ == '__main__':
    import sys
    c = CmdLineApp()
    sys.exit(c.cmdloop())
