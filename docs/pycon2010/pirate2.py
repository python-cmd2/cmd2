# coding=utf-8
from cmd import Cmd


# using ``do_`` methods

class Pirate(Cmd):
    gold = 3

    def do_loot(self, arg):
        'Seize booty from a passing ship.'
        self.gold += 1
        print('Now we gots {0} doubloons'
              .format(self.gold))

    def do_drink(self, arg):
        'Drown your sorrrows in rrrum.'
        self.gold -= 1
        print('Now we gots {0} doubloons'
              .format(self.gold))


pirate = Pirate()
pirate.cmdloop()
