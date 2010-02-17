from cmd2 import Cmd, options, make_option
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
            print('Now we gots {0} doubloons'.format(self.gold))
        if self.gold < 0:
            print("Off to debtorrr's prison.  Game overrr.")
            return True
        return stop
    def do_quit(self, arg):
        print("Quiterrr!")
        return True    
    default_to_shell = True
    multilineCommands = ['sing']
    terminators = Cmd.terminators + ['...']
    def do_sing(self, arg):
        print(self.colorize(arg, 'blue'))
    @options([make_option('--ho', type='int', help="How often to chant 'ho'", default=2),
              make_option('-c', '--commas', action="store_true", help="Interspers commas")])
    def do_yo(self, arg, opts):
        chant = ['yo'] + ['ho'] * opts.ho
        if opts.commas:
            separator = ', '
        else:
            separator = ' '
        print('{0} and a bottle of {1}'.format(separator.join(chant), arg))

pirate = Pirate()
pirate.cmdloop()