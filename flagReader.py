"""Defines and parses UNIX-style flags to modify command arguments.

print flagReader.FlagSet.parse.__doc__ for usage examples.
"""

import re

class Flag(object):
    def __init__(self, name, abbrev=None, nargs=0):
        """Flag(name, abbrev=None, nargs=0) : Defines a flag.
        
        name: the full name of the flag (double-dash form)
        abbrev: the single-letter abbreviated form of the flag; defaults to 
        nargs: number of arguments expected after the flag"""
        
        self.name = name
        self.abbrev = abbrev or name[0]
        self.fullabbrev = '-%s' % (self.abbrev)
        self.fullname = '--%s' % (name)
        self.nargs = nargs

class FlagSet(object):
    def __init__(self, flags):
        if not issubclass(type(flags), list):
            raise TypeError, 'Argument must be a list'
        self.flags = flags
        self.lookup = {}
        for flag in self.flags:
            self.lookup[flag.abbrev] = flag
            self.lookup[flag.fullabbrev] = flag
            self.lookup[flag.fullname] = flag
        self.abbrevPattern = re.compile('^-([%s]+)$' % (''.join(f.abbrev for f in flags)))
    def parse(self, arg):
        """
        Finds flags; returns {flag: (values, if any)} and the remaining argument.
        
        >>> f = FlagSet([Flag('foo'), Flag('bar'), Flag('gimmea', nargs=1)])
        >>> f.parse('-fb')
        ({'foo': [], 'bar': []}, '')
        >>> f.parse('no flags')
        ({}, 'no flags')
        >>> f.parse('-f blah')
        ({'foo': []}, 'blah')
        >>> f.parse('--bar')
        ({'bar': []}, '')
        >>> f.parse('--bar -f')
        ({'foo': [], 'bar': []}, '')
        >>> f.parse('--notaflag')
        ({}, '--notaflag')
        >>> f.parse('')
        ({}, '')
        >>> f.parse('--gimmea bee -f and then some other     stuff')
        ({'gimmea': ['bee'], 'foo': []}, 'and then some other stuff')
        >>> f.parse('hidden -bar')
        ({}, 'hidden -bar')
        >>> f.parse('-g myarg -b')
        ({'gimmea': ['myarg'], 'bar': []}, '')
        """
        result = {}
        words = arg.split()
        while words:
            word = words[0]
            flag = self.lookup.get(word)
            if flag:
                result[flag.name] = []
                words.pop(0)
                for arg in range(flag.nargs):
                    try:
                        result[flag.name].append(words.pop(0))
                    except IndexError: # there aren't as many args as we expect
                        raise IndexError, '%s expects %d arguments' % (word, flag.nargs)
                continue  # on to next word
            smashedAbbrevs = self.abbrevPattern.search(word)
            if smashedAbbrevs:
                for abbrev in smashedAbbrevs.group(1):
                    result[self.lookup[abbrev].name] = []
                words.pop(0)
                continue # on to next word
            #if you get to here, word[0] does not denote options
            break
        return result, ' '.join(words)

def _test():
    import doctest
    doctest.testmod()
    
if __name__ == '__main__':
    _test()