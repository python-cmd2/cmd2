"""Defines and parses UNIX-style flags to modify command arguments.

Use of flagReader is DEPRECATED in favor of optparse from the
Python standard library.  For backwards compatibility, flagReader
has been re-implemented as a wrapper around optparse.

print flagReader.FlagSet.parse.__doc__ for usage examples.
"""

import re, optparse, warnings
warnings.warn("""flagReader has been deprecated.  Use optparse instead.""", DeprecationWarning)

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
        parser = optparse.OptionParser()
        for flag in self.flags:
            if flag.nargs:
                parser.add_option(flag.fullabbrev, flag.fullname, action="store",
                                  type="string", dest=flag.name)
            else:
                parser.add_option(flag.fullabbrev, flag.fullname, action="store_true",
                                  dest=flag.name)
        try:
            (options, args) = parser.parse_args(arg.split())
        except SystemExit, e:
            return {}, arg
        
        result = {}
        for (k,v) in options.__dict__.items():
            if v == True:
                result[k] = []
            elif v:
                result[k] = [v]
        return result, ' '.join(args)

def _test():
    import doctest
    doctest.testmod()
    
if __name__ == '__main__':
    _test()