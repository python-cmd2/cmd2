from cmd import Cmd
# quitting

class Pirate(Cmd):
    gold = 3
    def do_loot(self, arg):
        'Drown your sorrrows in rrrum.'                
        self.gold += 1
    def do_drink(self, arg):
        '''Drown your sorrrows in rrrum.
        
        drink [n] - drink [n] barrel[s] o' rum.'''          
        try:
            self.gold -= int(arg)
        except:
            if arg:
                print '''What's "{0}"?  I'll take rrrum.'''.format(arg)
            self.gold -= 1                  
    def postcmd(self, stop, line):
        print 'Now we gots {0} doubloons'.format(self.gold)
        if self.gold < 0:
            print "Off to debtorrr's prrrison.  Game overrr."
            return True
        return stop
    def do_quit(self, arg):
        print "Quiterrr!"
        return True    

pirate = Pirate()
pirate.cmdloop()