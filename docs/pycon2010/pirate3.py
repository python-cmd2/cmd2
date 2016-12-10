# coding=utf-8
from cmd import Cmd


# using hook

class Pirate(Cmd):
    gold = 3

    def do_loot(self, arg):
        'Seize booty from a passing ship.'
        self.gold += 1

    def do_drink(self, arg):
        'Drown your sorrrows in rrrum.'
        self.gold -= 1

    def precmd(self, line):
        self.initial_gold = self.gold
        return line

    def postcmd(self, stop, line):
        if self.gold != self.initial_gold:
            print('Now we gots {0} doubloons'
                  .format(self.gold))


pirate = Pirate()
pirate.cmdloop()
