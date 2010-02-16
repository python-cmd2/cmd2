from cmd import Cmd
# using a hook

class Pirate(Cmd):
    gold = 3
    def do_loot(self, arg):
        'Drown your sorrrows in rrrum.'        
        self.gold += 1
    def do_drink(self, arg):
        'Drown your sorrrows in rrrum.'        
        self.gold -= 1
    def postcmd(self, stop, line):                         
        print 'Now we gots {0} doubloons'.format(self.gold)

pirate = Pirate()
pirate.cmdloop()