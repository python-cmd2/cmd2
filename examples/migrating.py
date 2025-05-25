#!/usr/bin/env python
"""A sample cmd application that shows how to trivially migrate a cmd application to use cmd2."""

# import cmd2 as cmd  # noqa: ERA001
import cmd  # Comment this line and uncomment the one above to migrate to cmd2
import random


class CmdLineApp(cmd.Cmd):
    """Example cmd application."""

    MUMBLES = ('like', '...', 'um', 'er', 'hmmm', 'ahh')
    MUMBLE_FIRST = ('so', 'like', 'well')
    MUMBLE_LAST = ('right?',)

    def do_exit(self, _line) -> bool:
        """Exit the application."""
        return True

    do_EOF = do_exit  # noqa: N815
    do_quit = do_exit

    def do_speak(self, line) -> None:
        """Repeats what you tell me to."""
        print(line, file=self.stdout)

    do_say = do_speak

    def do_mumble(self, line) -> None:
        """Mumbles what you tell me to."""
        words = line.split(' ')
        output = []
        if random.random() < 0.33:
            output.append(random.choice(self.MUMBLE_FIRST))
        for word in words:
            if random.random() < 0.40:
                output.append(random.choice(self.MUMBLES))
            output.append(word)
        if random.random() < 0.25:
            output.append(random.choice(self.MUMBLE_LAST))
        print(' '.join(output), file=self.stdout)


if __name__ == '__main__':
    import sys

    c = CmdLineApp()
    sys.exit(c.cmdloop())
