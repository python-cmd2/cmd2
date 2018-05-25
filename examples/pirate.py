#!/usr/bin/env python
# coding=utf-8
"""
This example is adapted from the pirate8.py example created by Catherine Devlin and
presented as part of her PyCon 2010 talk.

It demonstrates many features of cmd2.
"""
import argparse

import cmd2


class Pirate(cmd2.Cmd):
    """A piratical example cmd2 application involving looting and drinking."""
    def __init__(self):
        self.default_to_shell = True
        self.multiline_commands = ['sing']
        self.terminators = self.terminators + ['...']
        self.songcolor = 'blue'

        # Add stuff to settable and/or shortcuts before calling base class initializer
        self.settable['songcolor'] = 'Color to ``sing`` in (red/blue/green/cyan/magenta, bold, underline)'
        self.shortcuts.update({'~': 'sing'})

        """Initialize the base class as well as this one"""
        super().__init__()
        # prompts and defaults
        self.gold = 0
        self.initial_gold = self.gold
        self.prompt = 'arrr> '

    def precmd(self, line):
        """Runs just before a command line is parsed, but after the prompt is presented."""
        self.initial_gold = self.gold
        return line

    def postcmd(self, stop, line):
        """Runs right before a command is about to return."""
        if self.gold != self.initial_gold:
            self.poutput('Now we gots {0} doubloons'
                  .format(self.gold))
        if self.gold < 0:
            self.poutput("Off to debtorrr's prison.")
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
                self.poutput('''What's "{0}"?  I'll take rrrum.'''.format(arg))
            self.gold -= 1

    def do_quit(self, arg):
        """Quit the application gracefully."""
        self.poutput("Quiterrr!")
        return True

    def do_sing(self, arg):
        """Sing a colorful song."""
        self.poutput(self.colorize(arg, self.songcolor))

    yo_parser = argparse.ArgumentParser()
    yo_parser.add_argument('--ho', type=int, default=2, help="How often to chant 'ho'")
    yo_parser.add_argument('-c', '--commas', action='store_true', help='Intersperse commas')
    yo_parser.add_argument('beverage', help='beverage to drink with the chant')

    @cmd2.with_argparser(yo_parser)
    def do_yo(self, args):
        """Compose a yo-ho-ho type chant with flexible options."""
        chant = ['yo'] + ['ho'] * args.ho
        separator = ', ' if args.commas else ' '
        chant = separator.join(chant)
        self.poutput('{0} and a bottle of {1}'.format(chant, args.beverage))


if __name__ == '__main__':
    # Create an instance of the Pirate derived class and enter the REPL with cmdlooop().
    pirate = Pirate()
    pirate.cmdloop()
