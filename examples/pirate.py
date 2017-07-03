#!/usr/bin/env python
# coding=utf-8
"""
This example is adapted from the pirate8.py example created by Catherine Devlin and
presented as part of her PyCon 2010 talk.

It demonstrates many features of cmd2.
"""
from cmd2 import Cmd, options, make_option


class Pirate(Cmd):
    """A piratical example cmd2 application involving looting and drinking."""
    def __init__(self):
        self.default_to_shell = True
        self.multilineCommands = ['sing']
        self.terminators = Cmd.terminators + ['...']
        self.songcolor = 'blue'

        # Add stuff to settable and/or shortcuts before calling base class initializer
        self.settable['songcolor'] = 'Color to ``sing`` in (red/blue/green/cyan/magenta, bold, underline)'
        self.shortcuts.update({'~': 'sing'})

        """Initialize the base class as well as this one"""
        Cmd.__init__(self)
        # prompts and defaults
        self.gold = 3
        self.initial_gold = self.gold
        self.prompt = 'arrr> '

    def default(self, line):
        """This handles unknown commands."""
        print('What mean ye by "{0}"?'.format(line))

    def precmd(self, line):
        """Runs just before a command line is parsed, but after the prompt is presented."""
        self.initial_gold = self.gold
        return line

    def postcmd(self, stop, line):
        """Runs right before a command is about to return."""
        if self.gold != self.initial_gold:
            print('Now we gots {0} doubloons'
                  .format(self.gold))
        if self.gold < 0:
            print("Off to debtorrr's prison.")
            stop = True
        return stop

    # noinspection PyUnusedLocal
    def do_loot(self, arg):
        """Seize booty from a passing ship."""
        self.gold += 1

    def do_drink(self, arg):
        """Drown your sorrrows in rrrum.

        drink [n] - drink [n] barrel[s] o' rum."""
        try:
            self.gold -= int(arg)
        except ValueError:
            if arg:
                print('''What's "{0}"?  I'll take rrrum.'''.format(arg))
            self.gold -= 1

    def do_quit(self, arg):
        """Quit the application gracefully."""
        print("Quiterrr!")
        return True

    def do_sing(self, arg):
        """Sing a colorful song."""
        print(self.colorize(arg, self.songcolor))

    @options([make_option('--ho', type='int', default=2,
                          help="How often to chant 'ho'"),
              make_option('-c', '--commas',
                          action="store_true",
                          help="Intersperse commas")])
    def do_yo(self, arg, opts):
        """Compose a yo-ho-ho type chant with flexible options."""
        chant = ['yo'] + ['ho'] * opts.ho
        separator = ', ' if opts.commas else ' '
        chant = separator.join(chant)
        print('{0} and a bottle of {1}'.format(chant, arg))


if __name__ == '__main__':
    # Create an instance of the Pirate derived class and enter the REPL with cmdlooop().
    pirate = Pirate()
    pirate.cmdloop()
