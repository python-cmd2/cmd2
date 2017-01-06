# coding=utf-8
from cmd2 import Cmd


# prompts and defaults

class Pirate(Cmd):
    gold = 3
    prompt = 'arrr> '

    def default(self, line):
        print('What mean ye by "{0}"?'.format(line))

    def do_loot(self, arg):
        'Seize booty from a passing ship.'
        self.gold += 1

    def do_drink(self, arg):
        '''Drown your sorrrows in rrrum.

        drink [n] - drink [n] barrel[s] o' rum.'''
        try:
            self.gold -= int(arg)
        except:
            if arg:
                print('''What's "{0}"?  I'll take rrrum.'''.format(arg))
            self.gold -= 1

    def precmd(self, line):
        self.initial_gold = self.gold
        return line

    def postcmd(self, stop, line):
        if self.gold != self.initial_gold:
            print('Now we gots {0} doubloons'
                  .format(self.gold))
        if self.gold < 0:
            print("Off to debtorrr's prison.")
            stop = True
        return stop

    def do_quit(self, arg):
        print("Quiterrr!")
        return True

    default_to_shell = True
    multilineCommands = ['sing']
    terminators = Cmd.terminators + ['...']
    songcolor = 'blue'
    settable = Cmd.settable + 'songcolor Color to ``sing`` in (red/blue/green/cyan/magenta, bold, underline)'
    Cmd.shortcuts.update({'~': 'sing'})

    def do_sing(self, arg):
        print(self.colorize(arg, self.songcolor))


pirate = Pirate()
pirate.cmdloop()
